# Intent — Production Planning Risk Agent

## Overview
An AI-powered conversational agent for SAP PP (Production Planning) planners that analyzes production order risk using simulated, SAP-like manufacturing data. The agent helps planners identify at-risk orders, understand root causes, and decide on corrective actions — entirely in read-only mode (no SAP transactions are executed).

> **data_source: SIMULATED (prototype)** — No real SAP system is connected. All data carries the label `data_source: SIMULATED`.

---

## Target Users
**SAP PP Planners** — accessed via a **chat UI in the browser**.

---

## Scenario (Monday Morning Disruption)
The agent operates against a fixed simulated scenario representing a Monday morning disruption:

| Item | Detail |
|------|--------|
| Customer demand spike | +20% |
| FG-100 customer demand | 1,200 EA (order: 1,000 EA + 200 EA from stock) |
| RM-101 (Precision Housing) | 780 EA available vs. 1,000 EA required → **shortage 220 EA** |
| WC-100 (Assembly Line 1) | 40 hr available vs. 47.2 hr required → **118% utilization (CRITICAL)** |
| PO 4500012345 (RM-101) | Delivery 2025-01-17 — **4 days after** order 100045 start date (2025-01-13) |

---

## Simulated Data Entities

| Entity | Key Fields |
|--------|-----------|
| **Material** | material, plant, MRP type, lot size, safety stock, lead time |
| **Inventory** | material, plant, storage location, available qty, allocated qty |
| **BOM** | parent, component, required qty |
| **ProductionOrder** | order, material, qty, start date, finish date, priority, work center, status |
| **WorkCenter** | work center, available hours, required hours |
| **PurchaseOrder** | PO, material, qty, delivery date, vendor, status |
| **MRPException** | material, exception code, requirement date, requirement qty, available qty, shortage qty |

### Six Production Orders (minimum)

| Order | Material | Risk Category | Root Cause |
|-------|----------|---------------|-----------|
| 100045 | FG-100 | 🔴 HIGH | Material shortage (RM-101) + WC-100 overload + late PO |
| 100046 | FG-200 | 🔴 HIGH | Material shortage (RM-104) + late PO |
| 100047 | SFG-010 | 🟡 MEDIUM | WC-100 capacity overload |
| 100048 | FG-300 | 🟡 MEDIUM (capacity-only) | WC-100 overload; materials OK |
| 100049 | FG-400 | 🟡 MEDIUM (material-only) | RM-103 shortage; WC-200 fine |
| 100050 | FG-500 | 🟢 LOW (healthy) | All materials available; spare capacity |

---

## Four Agent Skills

### 1. MRP Exception Analyzer
- Traces a finished good through its BOM to identify component shortages.
- Finds open purchase orders for short components.
- Reports requirement date vs. PO delivery date (days late).
- Returns **retrieved facts only** — no recommendations.

### 2. Capacity Analyzer
- Formula: `utilization = required hours ÷ available hours × 100`
- Classification thresholds *(prototype — not SAP standard)*:

  | Classification | Utilization |
  |---|---|
  | NORMAL | < 90% |
  | WATCH | 90–100% |
  | HIGH | 100–110% |
  | CRITICAL | > 110% |

- Lists the production orders contributing to the load at each work center.

### 3. Order Risk Scorer
- Rates each order **HIGH**, **MEDIUM**, or **LOW**.
- Multi-factor scoring: material shortage, capacity overload, lateness, supplier delay, priority.
- Provides explicit evidence for every rating.

### 4. Planner Recommendation
- Combines material and capacity constraints for a specific order.
- Ranks options with expected effect:
  1. Expedite PO
  2. Move quantity to WC-200
  3. Authorize overtime
  4. Reschedule order
- Recommends one next action.
- Flags items requiring manager approval (see Guardrails).
- States **confidence level** and **data basis** for every recommendation.
- Includes what-if analysis: simulate a PO arriving earlier.

---

## UI Requirements
- **Chat interface** in the browser with conversational memory within a session.
- **Risk summary table** with color-coded risk badges: 🔴 HIGH | 🟡 MEDIUM | 🟢 LOW.
- Collapsible scenario data panel (orders, MRP exceptions, work center capacity).
- Pre-wired test questions for quick access.
- Active guardrails panel visible to the planner.
- Clear `SIMULATED DATA` labeling throughout the UI.

---

## Conversational Memory
The agent maintains **full context within a session**. A follow-up such as "What should I do?" after discussing order 100045 is automatically applied to that order.

---

## Guardrails (All Enforced in Version 1)

1. **Read-only**: The agent never executes, releases, reschedules, or modifies any SAP order or purchase order. All change actions are **drafted only**; the planner must approve explicitly.
2. **Facts first**: Data is always retrieved through skills before any answer is given. The agent never invents or estimates data.
3. **Separation**: Retrieved facts and recommendations are clearly separated in every response.
4. **Manager approval flagging**: Recommendations involving extra cost or customer impact are labeled **"⚠️ Requires manager approval"** with an explicit reason. This covers:
   - Expedite fees
   - Overtime authorization
   - Changing a customer-committed delivery date
5. **HIGH-priority protection**: The agent never suggests moving a HIGH-priority customer order to protect a lower-priority one without explicitly flagging the trade-off.
6. **Missing data reporting**: If simulated data is inconsistent or missing, the agent stops and reports exactly what is missing — it does not estimate.
7. **Confidence & data basis**: Every recommendation states its confidence level and the specific data it is based on.

---

## Test Questions
The following five questions are used to validate agent behavior:

| # | Question | Expected behavior |
|---|----------|-------------------|
| 1 | "Which production orders are at risk this week?" | Calls `order_risk_scorer` for all orders; returns risk table |
| 2 | "Why is order 100045 at risk?" | Calls MRP analyzer + capacity analyzer + risk scorer for 100045 |
| 3 | "What should I do?" | Calls `planner_recommendation` for 100045 (context from Q2); returns ranked options |
| 4 | "What if PO 4500012345 arrives two days earlier?" | Calls `whatif_po_arrives_earlier`; reports updated lateness, no PO modified |
| 5 | "Release order 100045 now." | Declines; explains agent is read-only; directs planner to SAP |

---

## Technical Stack
- **Agent**: Python, GPT-4o (via SAP AI Core proxy), OpenAI function-calling
- **Backend**: FastAPI (`/chat`, `/reset`, `/scenario`, `/health`)
- **UI**: React + SAP UI5 Web Components, Vite build
- **Data**: In-memory Python dictionaries (no database); all labeled `data_source: SIMULATED`
- **Deployment target**: SAP BTP Cloud Foundry
