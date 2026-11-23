"""
Production Planning Risk Agent
--------------------------------
Conversational AI agent for SAP PP planners.
Uses GPT-4o (via SAP AI Core proxy) with tool-calling for the four planning skills.

data_source: SIMULATED (prototype) — no real SAP system connected.

Guardrails enforced:
  - Never invent data: all facts retrieved through skills before answering.
  - Separate retrieved facts from recommendations.
  - Explain the reason for every recommendation.
  - Never execute any SAP transaction (read-only analysis only).
  - Flag recommendations needing manager approval.
  - Never de-prioritise a HIGH-priority customer order silently.
  - When data is missing, report exactly what is missing.
  - For every recommendation: state confidence and data basis.
"""

import json
import os
import re
from openai import OpenAI

import skills


# ---------------------------------------------------------------------------
# OpenAI client (SAP AI Core proxy)
# ---------------------------------------------------------------------------

AICORE_BASE_URL = os.environ.get("AICORE_BASE_URL", "")
AICORE_API_KEY  = os.environ.get("AICORE_API_KEY", "")
MODEL           = os.environ.get("PP_AGENT_MODEL", "gpt-4o")

client = OpenAI(
    base_url=AICORE_BASE_URL or None,   # None = use standard OpenAI endpoint
    api_key=AICORE_API_KEY,
)


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling schema)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "mrp_exception_analyzer",
            "description": (
                "Skill 1 — MRP Exception Analyzer. "
                "Traces a finished good (e.g. FG-100) through its BOM to identify "
                "component shortages and open purchase orders. Returns raw facts only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "finished_good": {
                        "type": "string",
                        "description": "Material number of the finished good (e.g. 'FG-100').",
                    }
                },
                "required": ["finished_good"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capacity_analyzer",
            "description": (
                "Skill 2 — Capacity Analyzer. "
                "Computes utilization = required ÷ available × 100 for work centers. "
                "Classifies: below 90% NORMAL, 90–100% WATCH, 100–110% HIGH, above 110% CRITICAL "
                "(prototype thresholds, not SAP standard). Lists contributing production orders. "
                "If work_center_id is omitted, analyzes all work centers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "work_center_id": {
                        "type": "string",
                        "description": "Work center ID (e.g. 'WC-100'). Omit to analyze all.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "order_risk_scorer",
            "description": (
                "Skill 3 — Order Risk Scorer. "
                "Rates each production order HIGH, MEDIUM, or LOW based on: "
                "material shortage, capacity overload, lateness, supplier delay, and priority. "
                "Returns evidence for each rating. "
                "If order_id is omitted, scores all orders."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Production order number (e.g. '100045'). Omit to score all.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planner_recommendation",
            "description": (
                "Skill 4 — Planner Recommendation. "
                "Combines material and capacity constraints for a specific order, "
                "ranks options (expedite PO, move qty to WC-200, reschedule, overtime), "
                "recommends one next action, flags items needing manager approval, "
                "and states confidence + data basis for every recommendation. "
                "READ-ONLY: drafts only. No SAP transaction is executed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Production order number (e.g. '100045').",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "whatif_po_arrives_earlier",
            "description": (
                "What-if analysis: simulates the effect of a purchase order "
                "arriving a specified number of days earlier than its current delivery date. "
                "Returns which orders would have their material risk resolved. "
                "No PO is modified — simulation only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "po_number": {
                        "type": "string",
                        "description": "Purchase order number (e.g. '4500012345').",
                    },
                    "days_earlier": {
                        "type": "integer",
                        "description": "Number of days earlier than current delivery date.",
                    },
                },
                "required": ["po_number", "days_earlier"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a Production Planning Risk Agent for SAP PP planners.

PERSONA
You are an expert SAP production planning analyst. You help planners identify at-risk 
production orders, understand root causes, and decide on corrective actions. 
You are analytical, precise, and conservative.

DATA SOURCE
ALL data is simulated (data_source: SIMULATED, prototype). No real SAP system is connected.
Always state this clearly when presenting facts. Never invent data — always retrieve it 
through the available tools before answering.

FOUR SKILLS (TOOLS)
1. mrp_exception_analyzer  — Trace a finished good → BOM → component shortages → open POs.
2. capacity_analyzer       — Utilization, classification, contributing orders.
3. order_risk_scorer       — Multi-factor risk rating (HIGH/MEDIUM/LOW) with evidence.
4. planner_recommendation  — Ranked options + one recommended next action.
5. whatif_po_arrives_earlier — Simulate effect of a PO arriving earlier.

RESPONSE FORMAT
- Always separate "RETRIEVED FACTS" from "ANALYSIS & RECOMMENDATIONS".
- For every recommendation, state: (a) the reason, (b) confidence level, (c) data basis.
- Use clear markdown with risk badges: 🔴 HIGH | 🟡 MEDIUM | 🟢 LOW.
- When presenting multiple orders, include a summary table.

GUARDRAILS — YOU MUST ALWAYS FOLLOW THESE:
1. NEVER invent or estimate data. If data is missing, state exactly what is missing.
2. Retrieve facts through tools BEFORE answering any factual question.
3. Separate retrieved facts from recommendations — never mix them.
4. NEVER execute, release, reschedule, or modify any SAP order or PO.
5. Any change action is a DRAFT ONLY. Planner must explicitly approve.
6. Flag recommendations with extra cost or customer impact as "⚠️ Requires manager approval" 
   and explain why (e.g., expedite fees, overtime, changing a customer-committed date).
7. NEVER move a HIGH-priority customer order to protect a lower-priority one without 
   explicitly flagging the trade-off.
8. For every recommendation, always state the confidence level and data basis.
9. If simulated data is inconsistent or missing, STOP and report it — do not estimate.
10. When asked to release or directly execute an order: DECLINE and explain that this agent 
    is read-only; the planner must use SAP directly.

CONVERSATION MEMORY
Maintain context across the conversation. If the planner says "What should I do?" after 
discussing order 100045, apply the recommendation to order 100045.

SCENARIO CONTEXT (Monday morning disruption):
- Customer demand +20%; FG-100 customer demand = 1,200 EA
- RM-101: 780 EA available vs. 1,000 EA required (shortage: 220 EA)
- WC-100: 40 hr available vs. 47.2 hr required (118% utilization — CRITICAL)
- Order 100045 for FG-100 on WC-100; PO 4500012345 for RM-101 due after requirement date
"""


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def _dispatch_tool(name: str, arguments: dict) -> str:
    if name == "mrp_exception_analyzer":
        result = skills.mrp_exception_analyzer(arguments["finished_good"])
    elif name == "capacity_analyzer":
        result = skills.capacity_analyzer(arguments.get("work_center_id"))
    elif name == "order_risk_scorer":
        result = skills.order_risk_scorer(arguments.get("order_id"))
    elif name == "planner_recommendation":
        result = skills.planner_recommendation(arguments["order_id"])
    elif name == "whatif_po_arrives_earlier":
        result = skills.whatif_po_arrives_earlier(
            arguments["po_number"], arguments["days_earlier"]
        )
    else:
        result = {"error": f"Unknown tool: {name}"}
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Agent (stateful session)
# ---------------------------------------------------------------------------

class ProductionPlanningAgent:
    """
    Maintains conversation history within a session.
    Each call to .chat() extends the history and returns the assistant reply.
    """

    def __init__(self):
        self.history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._last_order_context: str | None = None  # for follow-up resolution

    def _extract_order_context(self, text: str) -> str | None:
        """Extract an order number mentioned in the text for context carry-over."""
        m = re.search(r"\b(1\d{5})\b", text)
        return m.group(1) if m else None

    def chat(self, user_message: str) -> str:
        """Process a user message, calling tools as needed, and return the reply."""
        # Update context from user message
        order_in_msg = self._extract_order_context(user_message)
        if order_in_msg:
            self._last_order_context = order_in_msg

        self.history.append({"role": "user", "content": user_message})

        # Agentic loop
        for _ in range(10):  # max 10 iterations to prevent infinite loops
            response = client.chat.completions.create(
                model=MODEL,
                messages=self.history,
                tools=TOOLS,
                tool_choice="auto",
            )

            choice = response.choices[0]
            msg = choice.message

            # Append assistant message to history
            self.history.append(msg.model_dump(exclude_unset=False))

            # No tool call → final answer
            if choice.finish_reason == "stop" or not msg.tool_calls:
                return msg.content or ""

            # Execute all tool calls
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                tool_result = _dispatch_tool(tc.function.name, args)
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })

        return "I was unable to complete the analysis in the allowed number of steps. Please try a more specific question."

    def reset(self):
        """Reset conversation history (new session)."""
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._last_order_context = None
