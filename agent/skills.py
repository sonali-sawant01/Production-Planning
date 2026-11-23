"""
Production Planning Agent — Four Skills (all operating on simulated data).

Skills:
  1. MRPExceptionAnalyzer   – trace finished good → BOM → shortage → open POs
  2. CapacityAnalyzer        – utilization, classification, contributing orders
  3. OrderRiskScorer         – multi-factor risk rating per order
  4. PlannerRecommendation   – ranked options + one recommended next action

data_source: SIMULATED (prototype)
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
from data import (
    BOM, INVENTORY, MATERIALS, PRODUCTION_ORDERS,
    PURCHASE_ORDERS, WORK_CENTERS, MRP_EXCEPTIONS,
    DATA_SOURCE, SCENARIO_DATE,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _metadata(skill_name: str) -> dict:
    return {
        "data_source": DATA_SOURCE,
        "scenario_date": SCENARIO_DATE,
        "skill": skill_name,
        "disclaimer": "All data is simulated for prototype purposes only. "
                       "No real SAP system is connected.",
    }


def _get_order(order_id: str) -> dict | None:
    for o in PRODUCTION_ORDERS:
        if o["order"] == order_id:
            return o
    return None


def _inventory(material: str, plant: str = "1000") -> dict | None:
    return INVENTORY.get((material, plant))


def _bom_components(parent: str) -> list[dict]:
    return [b for b in BOM if b["parent"] == parent]


def _open_pos(material: str) -> list[dict]:
    return [po for po in PURCHASE_ORDERS if po["material"] == material and po["status"] == "OPEN"]


def _mrp_exceptions(material: str) -> list[dict]:
    return [ex for ex in MRP_EXCEPTIONS if ex["material"] == material]


def _days_late(requirement_date: str, delivery_date: str) -> int:
    from datetime import date
    fmt = "%Y-%m-%d"
    req = date.fromisoformat(requirement_date)
    dlv = date.fromisoformat(delivery_date)
    return max(0, (dlv - req).days)


# ---------------------------------------------------------------------------
# SKILL 1 — MRP Exception Analyzer
# ---------------------------------------------------------------------------

def mrp_exception_analyzer(finished_good: str) -> dict:
    """
    Trace a finished good through its BOM to component shortages and open POs.
    Returns retrieved facts only — no recommendations.
    """
    skill = "MRPExceptionAnalyzer"
    result: dict[str, Any] = {**_metadata(skill), "finished_good": finished_good}

    material = MATERIALS.get(finished_good)
    if material is None:
        result["error"] = f"Material '{finished_good}' not found in simulated data."
        return result

    result["material_master"] = material

    # BOM explosion (one level)
    components = _bom_components(finished_good)
    if not components:
        result["bom"] = []
        result["note"] = f"No BOM found for {finished_good} in simulated data."
        return result

    result["bom"] = components

    # Inventory & shortage check per component
    shortages = []
    for comp in components:
        mat = comp["component"]
        inv = _inventory(mat)
        if inv is None:
            shortages.append({
                "component": mat,
                "data_missing": True,
                "message": f"No inventory record found for {mat} in simulated data.",
            })
            continue

        # required qty for the scenario (use actual production order qty)
        orders_needing = [
            o for o in PRODUCTION_ORDERS
            if o["material"] == finished_good
        ]
        total_required = sum(
            o["qty"] * comp["required_qty"] for o in orders_needing
        )
        available = inv["available_qty"]
        shortage = max(0, total_required - available)

        entry = {
            "component": mat,
            "required_qty_per_parent": comp["required_qty"],
            "total_orders_qty": sum(o["qty"] for o in orders_needing),
            "total_required_qty": total_required,
            "available_qty": available,
            "shortage_qty": shortage,
            "has_shortage": shortage > 0,
            "open_purchase_orders": _open_pos(mat),
            "mrp_exceptions": _mrp_exceptions(mat),
        }

        # Late PO analysis
        if shortage > 0:
            pos = _open_pos(mat)
            if pos:
                late_pos = []
                for po in pos:
                    for o in orders_needing:
                        days = _days_late(o["start_date"], po["delivery_date"])
                        if days > 0:
                            late_pos.append({
                                "po": po["po"],
                                "delivery_date": po["delivery_date"],
                                "requirement_date": o["start_date"],
                                "days_late": days,
                                "po_qty": po["qty"],
                                "note": po.get("note", ""),
                            })
                entry["late_pos"] = late_pos
            else:
                entry["late_pos"] = []
                entry["po_warning"] = f"Shortage exists for {mat} but no open PO found."

        shortages.append(entry)

    result["component_analysis"] = shortages
    result["has_shortage"] = any(s.get("has_shortage") for s in shortages if not s.get("data_missing"))
    return result


# ---------------------------------------------------------------------------
# SKILL 2 — Capacity Analyzer
# ---------------------------------------------------------------------------

# Prototype thresholds (not SAP standard)
_CAPACITY_THRESHOLDS = {
    "NORMAL":   (0.0,  90.0),
    "WATCH":    (90.0, 100.0),
    "HIGH":     (100.0, 110.0),
    "CRITICAL": (110.0, float("inf")),
}

def _classify_utilization(pct: float) -> str:
    for label, (lo, hi) in _CAPACITY_THRESHOLDS.items():
        if lo <= pct < hi:
            return label
    return "CRITICAL"


def capacity_analyzer(work_center_id: str | None = None) -> dict:
    """
    Compute utilization for all (or one) work center(s), classify, and list
    contributing production orders. Returns retrieved facts only.
    """
    skill = "CapacityAnalyzer"
    result: dict[str, Any] = {
        **_metadata(skill),
        "classification_thresholds": {
            "NORMAL": "below 90%",
            "WATCH": "90–100%",
            "HIGH": "100–110%",
            "CRITICAL": "above 110%",
            "disclaimer": "Prototype thresholds — not SAP standard",
        },
    }

    wcs = WORK_CENTERS if work_center_id is None else {
        work_center_id: WORK_CENTERS.get(work_center_id)
    }

    if work_center_id and WORK_CENTERS.get(work_center_id) is None:
        result["error"] = f"Work center '{work_center_id}' not found in simulated data."
        return result

    analyses = []
    for wc_id, wc in wcs.items():
        if wc is None:
            analyses.append({"work_center": wc_id, "error": "Not found in simulated data."})
            continue

        pct = (wc["required_hours"] / wc["available_hours"]) * 100 if wc["available_hours"] > 0 else 0
        classification = _classify_utilization(pct)

        contributing_orders = [
            {
                "order": o["order"],
                "material": o["material"],
                "scheduled_hours": o["scheduled_hours"],
                "priority": o["priority"],
                "status": o["status"],
                "start_date": o["start_date"],
                "finish_date": o["finish_date"],
            }
            for o in PRODUCTION_ORDERS
            if o["work_center"] == wc_id
        ]

        hour_deficit = max(0.0, wc["required_hours"] - wc["available_hours"])

        analyses.append({
            "work_center": wc_id,
            "description": wc["description"],
            "available_hours": wc["available_hours"],
            "required_hours": wc["required_hours"],
            "utilization_pct": round(pct, 1),
            "classification": classification,
            "hour_deficit": round(hour_deficit, 1),
            "contributing_orders": contributing_orders,
            "total_contributing_orders": len(contributing_orders),
        })

    result["work_center_analysis"] = analyses
    return result


# ---------------------------------------------------------------------------
# SKILL 3 — Order Risk Scorer
# ---------------------------------------------------------------------------

def _score_order(order: dict) -> dict:
    """Compute a multi-factor risk score for a single production order."""
    factors = []
    score_points = 0  # accumulate evidence weight

    # Factor 1: Material shortage
    components = _bom_components(order["material"])
    material_shortage = False
    shortage_details = []
    for comp in components:
        inv = _inventory(comp["component"])
        if inv is None:
            factors.append({
                "factor": "MATERIAL_DATA_MISSING",
                "severity": "UNKNOWN",
                "detail": f"No inventory for component {comp['component']}.",
            })
            score_points += 2
            continue
        required = order["qty"] * comp["required_qty"]
        avail = inv["available_qty"]
        shortage = max(0, required - avail)
        if shortage > 0:
            material_shortage = True
            score_points += 3
            shortage_details.append({
                "component": comp["component"],
                "required": required,
                "available": avail,
                "shortage": shortage,
            })
    if shortage_details:
        factors.append({
            "factor": "MATERIAL_SHORTAGE",
            "severity": "HIGH",
            "detail": shortage_details,
        })

    # Factor 2: Capacity overload at the work center
    wc = WORK_CENTERS.get(order["work_center"])
    if wc:
        pct = (wc["required_hours"] / wc["available_hours"]) * 100
        classification = _classify_utilization(pct)
        if classification in ("HIGH", "CRITICAL"):
            overload_pts = 2 if classification == "HIGH" else 3
            score_points += overload_pts
            factors.append({
                "factor": "CAPACITY_OVERLOAD",
                "severity": classification,
                "detail": f"{order['work_center']} at {round(pct, 1)}% utilization ({classification}).",
            })
    else:
        factors.append({
            "factor": "WORK_CENTER_DATA_MISSING",
            "severity": "UNKNOWN",
            "detail": f"No data for work center {order['work_center']}.",
        })
        score_points += 1

    # Factor 3: Late PO / supplier delay
    late_supplier = False
    for comp in components:
        for po in _open_pos(comp["component"]):
            days = _days_late(order["start_date"], po["delivery_date"])
            if days > 0:
                late_supplier = True
                score_points += 2
                factors.append({
                    "factor": "SUPPLIER_DELAY",
                    "severity": "HIGH",
                    "detail": f"PO {po['po']} for {comp['component']} is {days} day(s) late "
                              f"(need by {order['start_date']}, arrives {po['delivery_date']}).",
                })

    # Factor 4: Priority — HIGH priority elevates the risk rating
    if order["priority"] == 1:
        factors.append({
            "factor": "HIGH_PRIORITY_ORDER",
            "severity": "INFO",
            "detail": f"Order has priority {order['priority']} — customer-facing impact.",
        })
        score_points += 1

    # Determine overall risk rating
    if score_points >= 6:
        rating = "HIGH"
    elif score_points >= 3:
        rating = "MEDIUM"
    else:
        rating = "LOW"

    return {
        "order": order["order"],
        "material": order["material"],
        "qty": order["qty"],
        "work_center": order["work_center"],
        "status": order["status"],
        "priority": order["priority"],
        "start_date": order["start_date"],
        "finish_date": order["finish_date"],
        "risk_rating": rating,
        "score_points": score_points,
        "risk_factors": factors,
        "note": order.get("note", ""),
    }


def order_risk_scorer(order_id: str | None = None) -> dict:
    """
    Rate each production order HIGH / MEDIUM / LOW with evidence.
    If order_id supplied, scores only that order.
    """
    skill = "OrderRiskScorer"
    result: dict[str, Any] = {**_metadata(skill)}

    orders = PRODUCTION_ORDERS if order_id is None else [
        o for o in PRODUCTION_ORDERS if o["order"] == order_id
    ]

    if order_id and not orders:
        result["error"] = f"Order '{order_id}' not found in simulated data."
        return result

    scored = [_score_order(o) for o in orders]
    scored.sort(key=lambda x: x["score_points"], reverse=True)

    result["order_risk_analysis"] = scored
    result["summary"] = {
        "total_orders": len(scored),
        "high_risk": sum(1 for s in scored if s["risk_rating"] == "HIGH"),
        "medium_risk": sum(1 for s in scored if s["risk_rating"] == "MEDIUM"),
        "low_risk": sum(1 for s in scored if s["risk_rating"] == "LOW"),
    }
    return result


# ---------------------------------------------------------------------------
# SKILL 4 — Planner Recommendation
# ---------------------------------------------------------------------------

def planner_recommendation(order_id: str) -> dict:
    """
    Combine material + capacity constraints for a specific order, rank options,
    recommend one next action, and flag items that require manager approval.
    Read-only: drafts only. Planner must approve any change.
    """
    skill = "PlannerRecommendation"
    result: dict[str, Any] = {**_metadata(skill), "order_id": order_id}

    order = _get_order(order_id)
    if order is None:
        result["error"] = f"Order '{order_id}' not found in simulated data."
        return result

    result["order"] = order

    # Pull facts from the other skills
    mrp_facts = mrp_exception_analyzer(order["material"])
    cap_facts = capacity_analyzer(order["work_center"])
    risk_facts = order_risk_scorer(order_id)

    result["retrieved_facts"] = {
        "mrp_analysis": mrp_facts,
        "capacity_analysis": cap_facts,
        "risk_analysis": risk_facts,
    }

    # Build ranked options
    options = []

    scored = risk_facts.get("order_risk_analysis", [{}])
    scored_order = scored[0] if scored else {}
    factors = scored_order.get("risk_factors", [])
    factor_types = [f["factor"] for f in factors]

    has_material_shortage = "MATERIAL_SHORTAGE" in factor_types
    has_capacity_overload = "CAPACITY_OVERLOAD" in factor_types
    has_supplier_delay = "SUPPLIER_DELAY" in factor_types

    if has_supplier_delay:
        options.append({
            "rank": 1,
            "option": "EXPEDITE_PO",
            "description": "Contact vendor to request early delivery of open PO(s).",
            "expected_effect": "Closes material shortage; allows order to start on original date.",
            "constraints": "May incur expedite fees.",
            "requires_manager_approval": True,
            "approval_reason": "Expedite fees represent additional cost — requires manager approval.",
            "confidence": "HIGH",
            "data_basis": "PO delivery dates vs. order requirement dates from simulated purchase orders.",
        })

    if has_capacity_overload:
        wc = WORK_CENTERS.get(order["work_center"])
        alt_wc_id = "WC-200"
        alt_wc = WORK_CENTERS.get(alt_wc_id)
        if alt_wc:
            alt_pct = (alt_wc["required_hours"] / alt_wc["available_hours"]) * 100
            spare_hours = alt_wc["available_hours"] - alt_wc["required_hours"]
            options.append({
                "rank": 2,
                "option": "MOVE_QTY_TO_ALT_WORK_CENTER",
                "description": f"Split or move a lower-priority order from {order['work_center']} to {alt_wc_id}.",
                "expected_effect": (
                    f"Reduces {order['work_center']} load; {alt_wc_id} has "
                    f"{round(spare_hours, 1)} spare hours ({round(alt_pct, 1)}% utilization)."
                ),
                "constraints": (
                    "Only applicable to orders/materials compatible with WC-200 capabilities. "
                    "Check routing before moving."
                ),
                "requires_manager_approval": False,
                "confidence": "MEDIUM",
                "data_basis": "Work center utilization from simulated work center data.",
            })

    if has_capacity_overload:
        wc_data = WORK_CENTERS.get(order["work_center"])
        hour_deficit = round(max(0.0, wc_data["required_hours"] - wc_data["available_hours"]), 1) if wc_data else "?"
        options.append({
            "rank": 3,
            "option": "AUTHORIZE_OVERTIME",
            "description": f"Approve overtime on {order['work_center']} to cover the {hour_deficit}-hour deficit.",
            "expected_effect": "Eliminates capacity overload without rescheduling any orders.",
            "constraints": "Overtime increases labor cost and may impact worker availability next week.",
            "requires_manager_approval": True,
            "approval_reason": "Overtime cost and customer-committed schedule impact require manager approval.",
            "confidence": "HIGH",
            "data_basis": f"WC-100 required {WORK_CENTERS.get(order['work_center'], {}).get('required_hours', '?')} hr vs. available {WORK_CENTERS.get(order['work_center'], {}).get('available_hours', '?')} hr.",
        })

    options.append({
        "rank": len(options) + 1,
        "option": "RESCHEDULE_ORDER",
        "description": "Push finish date out to after the confirmed PO delivery date.",
        "expected_effect": "Eliminates material shortage risk; may delay customer shipment.",
        "constraints": "Changing a customer-committed date requires customer notification.",
        "requires_manager_approval": order.get("customer_order") is not None,
        "approval_reason": "Rescheduling a customer-committed order requires manager approval and customer communication.",
        "confidence": "HIGH" if has_material_shortage else "MEDIUM",
        "data_basis": "Order finish date vs. PO delivery date from simulated data.",
    })

    # Rank best option (lowest rank = best)
    options.sort(key=lambda x: x["rank"])

    # Recommended action: expedite PO if feasible; else move WC; else overtime; else reschedule
    recommended = options[0] if options else None

    # Tradeoff warnings
    tradeoffs = []
    if has_capacity_overload and order["priority"] == 1:
        lower_prio_orders = [
            o for o in PRODUCTION_ORDERS
            if o["work_center"] == order["work_center"] and o["priority"] > order["priority"]
        ]
        if lower_prio_orders:
            tradeoffs.append({
                "warning": "HIGH_PRIORITY_PROTECTION",
                "detail": (
                    f"Order {order_id} (priority {order['priority']}) must not be delayed "
                    f"to protect lower-priority orders: "
                    + ", ".join(f"{o['order']} (priority {o['priority']})" for o in lower_prio_orders)
                    + ". Any resequencing that disadvantages this order requires explicit planner approval."
                ),
            })

    result["ranked_options"] = options
    result["recommended_next_action"] = recommended
    result["tradeoff_warnings"] = tradeoffs
    result["read_only_notice"] = (
        "This is a draft recommendation only. The agent cannot execute, reschedule, "
        "release, or modify any SAP order or purchase order. All actions require "
        "explicit planner (and where flagged, manager) approval."
    )

    return result


# ---------------------------------------------------------------------------
# Convenience: what-if analysis
# ---------------------------------------------------------------------------

def whatif_po_arrives_earlier(po_number: str, days_earlier: int) -> dict:
    """
    Simulate the effect of a PO arriving `days_earlier` days before its
    current scheduled delivery date.
    """
    from datetime import date, timedelta

    skill = "WhatIfAnalysis"
    result: dict[str, Any] = {**_metadata(skill), "po": po_number, "days_earlier": days_earlier}

    po = next((p for p in PURCHASE_ORDERS if p["po"] == po_number), None)
    if po is None:
        result["error"] = f"PO '{po_number}' not found in simulated data."
        return result

    result["original_po"] = po

    original_date = date.fromisoformat(po["delivery_date"])
    new_date = original_date - timedelta(days=days_earlier)
    result["simulated_delivery_date"] = str(new_date)

    # Find orders requiring this material
    affected_orders = [
        o for o in PRODUCTION_ORDERS
        if any(c["component"] == po["material"] for c in _bom_components(o["material"]))
    ]

    impact = []
    for o in affected_orders:
        req_date = date.fromisoformat(o["start_date"])
        originally_late = (original_date - req_date).days
        now_late = (new_date - req_date).days
        impact.append({
            "order": o["order"],
            "material": o["material"],
            "requirement_date": o["start_date"],
            "original_delivery_date": str(original_date),
            "simulated_delivery_date": str(new_date),
            "originally_days_late": max(0, originally_late),
            "simulated_days_late": max(0, now_late),
            "risk_resolved": now_late <= 0,
            "note": (
                "PO would arrive on time — material risk resolved."
                if now_late <= 0
                else f"PO still {now_late} day(s) late even with early delivery."
            ),
        })

    result["affected_orders"] = impact
    result["whatif_note"] = (
        f"Simulated scenario only. No PO has been modified. "
        f"Actual PO {po_number} delivery date remains {po['delivery_date']}."
    )
    return result
