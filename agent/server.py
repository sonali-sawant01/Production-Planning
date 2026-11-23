"""
FastAPI server for the Production Planning Risk Agent.
Exposes:
  POST /chat   — send a message, receive a reply (session-scoped)
  POST /reset  — clear conversation history
  GET  /health — liveness check
  GET  /scenario — return scenario context

data_source: SIMULATED (prototype)
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import ProductionPlanningAgent
from data import (
    DEMAND_CONTEXT, PRODUCTION_ORDERS, WORK_CENTERS,
    MRP_EXCEPTIONS, PURCHASE_ORDERS, DATA_SOURCE, SCENARIO_DATE,
)

app = FastAPI(
    title="Production Planning Risk Agent",
    description="SAP PP planner risk analysis agent (simulated data, prototype)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session store (in-memory; single-user prototype)
_sessions: dict[str, ProductionPlanningAgent] = {}


def _get_or_create_agent(session_id: str) -> ProductionPlanningAgent:
    if session_id not in _sessions:
        _sessions[session_id] = ProductionPlanningAgent()
    return _sessions[session_id]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class ResetRequest(BaseModel):
    session_id: str = "default"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "data_source": DATA_SOURCE, "scenario_date": SCENARIO_DATE}


@app.get("/scenario")
def get_scenario():
    """Return the scenario context for display in the UI."""
    return {
        "data_source": DATA_SOURCE,
        "disclaimer": "All data is simulated for prototype purposes only.",
        "demand_context": DEMAND_CONTEXT,
        "production_orders": PRODUCTION_ORDERS,
        "work_centers": list(WORK_CENTERS.values()),
        "mrp_exceptions": MRP_EXCEPTIONS,
        "purchase_orders": PURCHASE_ORDERS,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    agent = _get_or_create_agent(req.session_id)
    try:
        reply = agent.chat(req.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return ChatResponse(reply=reply, session_id=req.session_id)


@app.post("/reset")
def reset(req: ResetRequest):
    agent = _get_or_create_agent(req.session_id)
    agent.reset()
    return {"status": "reset", "session_id": req.session_id}
