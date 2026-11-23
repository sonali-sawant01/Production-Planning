# Specification — Production Planning Risk Agent

> **data_source: SIMULATED (prototype)** — No real SAP system is connected.
> Version: 1.0.0 | Scenario date: 2025-01-13

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Simulated Data Model](#3-simulated-data-model)
4. [Skill Specifications](#4-skill-specifications)
   - 4.1 MRP Exception Analyzer
   - 4.2 Capacity Analyzer
   - 4.3 Order Risk Scorer
   - 4.4 Planner Recommendation
   - 4.5 What-If Analysis
5. [Agent Specification](#5-agent-specification)
6. [API Specification](#6-api-specification)
7. [UI Specification](#7-ui-specification)
8. [Guardrail Implementation](#8-guardrail-implementation)
9. [Scoring & Classification Logic](#9-scoring--classification-logic)
10. [Error Handling](#10-error-handling)
11. [File Structure](#11-file-structure)
12. [Environment & Configuration](#12-environment--configuration)
13. [Deployment](#13-deployment)

---

## 1. System Overview

The Production Planning Risk Agent is a browser-based conversational AI assistant for SAP PP planners. It operates entirely on **simulated, in-memory manufacturing data** (no real SAP connection) and is **strictly read-only** — it analyzes and recommends but never executes any SAP transaction.

### Core flow

```
Planner types a question in the browser
        ↓
React UI  →  POST /chat  →  FastAPI server
                                  ↓
                        ProductionPlanningAgent.chat()
                                  ↓
                     GPT-4o (SAP AI Core proxy)
                       ↙         ↓          ↘
              skill tool    skill tool    skill tool
              (Python)      (Python)      (Python)
                       ↘         ↓          ↙
                        in-memory data layer
                       (data.py — SIMULATED)
                                  ↓
                     Formatted markdown reply
                                  ↓
React UI renders response with risk badges & tables
```

---

## 2. Architecture

### 2.1 Components

| Component | Technology | Location | Purpose |
|-----------|-----------|----------|---------|
| **Data layer** | Python dicts | `agent/data.py` | All simulated SAP-like data |
| **Skills** | Python functions | `agent/skills.py` | Four deterministic planning skills + what-if |
| **Agent** | Python + OpenAI SDK | `agent/agent.py` | GPT-4o conversational agent with tool-calling |
| **API server** | FastAPI | `agent/server.py` | REST endpoints for the UI |
| **Entry point** | Python | `agent/main.py` | Starts server; serves built UI static files |
| **UI** | React + Vite | `ui/src/` | Chat interface with markdown and risk tables |
| **UI build output** | Static HTML/JS/CSS | `agent/static/` | Built React app served by FastAPI |

### 2.2 Runtime process

A single Python process (`uvicorn`) serves:
- All API routes (`/chat`, `/reset`, `/scenario`, `/health`)
- The built React app as static files from `/`

No database, no message queue, no external services beyond the SAP AI Core LLM proxy.

### 2.3 Session model

Sessions are keyed by `session_id` (string). Each session holds one `ProductionPlanningAgent` instance with its own conversation `history` list. Sessions are stored in a Python dict in memory — they are lost on server restart. This is acceptable for a prototype.

---

## 3. Simulated Data Model

All data lives in `agent/data.py`. Every record is read-only. All records carry `data_source: SIMULATED` and `scenario_date: 2025-01-13`.

### 3.1 Constants

```python
DATA_SOURCE   = "SIMULATED"
SCENARIO_DATE = "2025-01-13"   # Monday morning reference date
```

### 3.2 Material master

Storage: `dict[str, dict]` keyed by material number.

| Field | Type | Description |
|-------|------|-------------|
| `material` | str | Material number (e.g. `"FG-100"`) |
| `description` | str | Human-readable description |
| `plant` | str | Plant code (`"1000"`) |
| `mrp_type` | str | MRP type (`"PD"` = MRP, `"FX"` = fixed) |
| `lot_size` | str | Lot sizing (`"EX"` = exact, `"FX"` = fixed) |
| `safety_stock` | int | Safety stock quantity in EA |
| `lead_time_days` | int | Procurement/production lead time |
| `unit` | str | Base unit of measure (`"EA"`) |

**Materials defined:** FG-100, FG-200, SFG-010, FG-300, FG-400, FG-500, RM-101, RM-102, RM-103, RM-104, RM-105, RM-106.

### 3.3 Inventory

Storage: `dict[tuple[str,str], dict]` keyed by `(material, plant)`.

| Field | Type | Description |
|-------|------|-------------|
| `material` | str | Material number |
| `plant` | str | Plant code |
| `storage_location` | str | Storage location (`"0001"`) |
| `available_qty` | int | Unrestricted stock available |
| `allocated_qty` | int | Quantity already allocated to orders |
| `unit` | str | `"EA"` |

**Key shortage values:**

| Material | Available | Scenario Requirement | Shortage |
|----------|-----------|---------------------|---------|
| RM-101 | 780 EA | 1,000 EA | **220 EA** |
| RM-103 | 150 EA | 300 EA | **150 EA** |
| RM-104 | 1,450 EA | 1,600 EA | **150 EA** |

### 3.4 Bill of Materials (BOM)

Storage: `list[dict]` — flat list of BOM lines.

| Field | Type | Description |
|-------|------|-------------|
| `parent` | str | Parent material number |
| `component` | str | Component material number |
| `required_qty` | int | Quantity of component per 1 parent |
| `unit` | str | `"EA"` |

**BOM lines:**

| Parent | Component | Qty/Parent |
|--------|-----------|-----------|
| FG-100 | RM-101 | 1 |
| FG-100 | RM-102 | 2 |
| FG-200 | RM-104 | 2 |
| SFG-010 | RM-102 | 1 |
| SFG-010 | RM-105 | 1 |
| FG-300 | RM-105 | 1 |
| FG-300 | RM-106 | 1 |
| FG-400 | RM-103 | 1 |
| FG-500 | RM-105 | 2 |
| FG-500 | RM-106 | 1 |

### 3.5 Production Orders

Storage: `list[dict]`.

| Field | Type | Description |
|-------|------|-------------|
| `order` | str | Order number |
| `material` | str | Finished/semi-finished good |
| `qty` | int | Order quantity |
| `unit` | str | `"EA"` |
| `start_date` | str | ISO date `"YYYY-MM-DD"` |
| `finish_date` | str | ISO date `"YYYY-MM-DD"` |
| `priority` | int | 1 = highest, 3 = lowest |
| `work_center` | str | Assigned work center |
| `status` | str | `"RELEASED"` or `"PLANNED"` |
| `scheduled_hours` | float | Hours this order contributes to WC load |
| `customer_order` | str \| None | Linked sales order number, if any |
| `note` | str | Scenario annotation |

**The six orders:**

| Order | Material | Qty | Start | Finish | Priority | WC | Status | Hours | Risk |
|-------|----------|-----|-------|--------|----------|----|--------|-------|------|
| 100045 | FG-100 | 1,000 | 2025-01-13 | 2025-01-17 | 1 | WC-100 | RELEASED | 24.0 | 🔴 HIGH |
| 100046 | FG-200 | 800 | 2025-01-13 | 2025-01-16 | 1 | WC-100 | RELEASED | 16.0 | 🔴 HIGH |
| 100047 | SFG-010 | 500 | 2025-01-14 | 2025-01-18 | 2 | WC-100 | PLANNED | 4.0 | 🟡 MEDIUM |
| 100048 | FG-300 | 300 | 2025-01-13 | 2025-01-16 | 3 | WC-100 | RELEASED | 3.2 | 🟡 MEDIUM |
| 100049 | FG-400 | 300 | 2025-01-14 | 2025-01-20 | 2 | WC-200 | PLANNED | 12.0 | 🟡 MEDIUM |
| 100050 | FG-500 | 200 | 2025-01-15 | 2025-01-20 | 3 | WC-200 | PLANNED | 10.0 | 🟢 LOW |

### 3.6 Work Centers

Storage: `dict[str, dict]` keyed by work center ID.

| Field | Type | Description |
|-------|------|-------------|
| `work_center` | str | Work center ID |
| `description` | str | Human-readable name |
| `plant` | str | Plant code |
| `available_hours` | float | Total hours available this week |
| `required_hours` | float | Total hours demanded by all orders |
| `unit` | str | `"HR"` |

| WC | Available | Required | Utilization | Classification |
|----|-----------|----------|-------------|----------------|
| WC-100 | 40.0 hr | 47.2 hr | **118.0%** | **CRITICAL** |
| WC-200 | 32.0 hr | 22.0 hr | **68.75%** | **NORMAL** |

### 3.7 Purchase Orders

Storage: `list[dict]`.

| Field | Type | Description |
|-------|------|-------------|
| `po` | str | PO number |
| `material` | str | Material being purchased |
| `qty` | int | PO quantity |
| `unit` | str | `"EA"` |
| `delivery_date` | str | ISO date — confirmed delivery |
| `vendor` | str | Vendor code |
| `vendor_name` | str | Vendor display name |
| `status` | str | `"OPEN"` |
| `note` | str | Scenario annotation |

| PO | Material | Qty | Delivery | Requirement | Days Late |
|----|----------|-----|----------|-------------|-----------|
| 4500012345 | RM-101 | 300 | 2025-01-17 | 2025-01-13 | **4** |
| 4500012346 | RM-104 | 300 | 2025-01-17 | 2025-01-14 | **3** |
| 4500012347 | RM-103 | 200 | 2025-01-18 | 2025-01-14 | **4** |

### 3.8 MRP Exceptions

Storage: `list[dict]`.

| Field | Type | Description |
|-------|------|-------------|
| `material` | str | Material number |
| `plant` | str | Plant code |
| `exception_code` | str | SAP-style exception code |
| `exception_text` | str | Human-readable exception |
| `requirement_date` | str | ISO date when material is needed |
| `requirement_qty` | int | Total qty needed |
| `available_qty` | int | Qty on hand |
| `shortage_qty` | int | `requirement_qty - available_qty` |
| `unit` | str | `"EA"` |
| `open_po` | str | Linked open PO number |

| Material | Req Date | Required | Available | Shortage | Linked PO |
|----------|----------|----------|-----------|---------|-----------|
| RM-101 | 2025-01-13 | 1,000 | 780 | **220** | 4500012345 |
| RM-104 | 2025-01-14 | 1,600 | 1,450 | **150** | 4500012346 |
| RM-103 | 2025-01-14 | 300 | 150 | **150** | 4500012347 |

---

## 4. Skill Specifications

All skills are pure Python functions in `agent/skills.py`. They read exclusively from `data.py`. They are deterministic (no randomness, no LLM calls). They are called via OpenAI function-calling from `agent.py`.

Every skill response includes a metadata envelope:

```json
{
  "data_source": "SIMULATED",
  "scenario_date": "2025-01-13",
  "skill": "<SkillName>",
  "disclaimer": "All data is simulated for prototype purposes only. No real SAP system is connected."
}
```

---

### 4.1 MRP Exception Analyzer

**Function:** `mrp_exception_analyzer(finished_good: str) -> dict`

**Purpose:** Trace a finished good → BOM components → inventory → shortage → open POs → late POs. Returns facts only.

#### Input

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `finished_good` | str | Yes | Material number, e.g. `"FG-100"` |

#### Algorithm

```
1. Look up finished_good in MATERIALS
   → If not found: return error field, stop

2. Look up BOM lines where parent == finished_good
   → If none: return bom=[], note="No BOM found", stop

3. For each BOM component:
   a. Look up inventory record (material, plant="1000")
      → If not found: append data_missing=True entry, continue

   b. Find all production orders for this finished_good
   c. total_required = sum(order.qty × comp.required_qty) for all orders
   d. shortage = max(0, total_required - available_qty)
   e. has_shortage = (shortage > 0)

   f. If has_shortage:
      - Find all OPEN purchase orders for this component
      - For each PO, for each order needing this FG:
          days_late = max(0, PO.delivery_date - order.start_date)
          If days_late > 0: append to late_pos list
      - If no open POs: append po_warning

4. Return component_analysis list + has_shortage boolean
```

#### Output schema

```json
{
  "data_source": "SIMULATED",
  "scenario_date": "2025-01-13",
  "skill": "MRPExceptionAnalyzer",
  "disclaimer": "...",
  "finished_good": "FG-100",
  "material_master": { ... },
  "bom": [ { "parent": "FG-100", "component": "RM-101", "required_qty": 1, "unit": "EA" }, ... ],
  "component_analysis": [
    {
      "component": "RM-101",
      "required_qty_per_parent": 1,
      "total_orders_qty": 1000,
      "total_required_qty": 1000,
      "available_qty": 780,
      "shortage_qty": 220,
      "has_shortage": true,
      "open_purchase_orders": [ { "po": "4500012345", ... } ],
      "mrp_exceptions": [ { ... } ],
      "late_pos": [
        {
          "po": "4500012345",
          "delivery_date": "2025-01-17",
          "requirement_date": "2025-01-13",
          "days_late": 4,
          "po_qty": 300,
          "note": "..."
        }
      ]
    }
  ],
  "has_shortage": true
}
```

#### Error cases

| Condition | Response field |
|-----------|---------------|
| Material not in MATERIALS | `"error": "Material 'X' not found in simulated data."` |
| No BOM lines for material | `"bom": [], "note": "No BOM found for X in simulated data."` |
| No inventory for a component | Component entry has `"data_missing": true, "message": "No inventory record found for X in simulated data."` |
| Shortage but no open PO | Component entry has `"po_warning": "Shortage exists for X but no open PO found."` |

---

### 4.2 Capacity Analyzer

**Function:** `capacity_analyzer(work_center_id: str | None = None) -> dict`

**Purpose:** Compute utilization for one or all work centers, classify, list contributing orders.

#### Input

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `work_center_id` | str \| None | No | Work center ID. If `None`, analyze all. |

#### Algorithm

```
1. If work_center_id provided:
   → If not in WORK_CENTERS: return error, stop

2. For each work center:
   a. utilization_pct = (required_hours / available_hours) × 100
   b. classification = classify(utilization_pct)   [see §9.1]
   c. hour_deficit = max(0, required_hours - available_hours)
   d. contributing_orders = all PRODUCTION_ORDERS where work_center == wc_id

3. Return work_center_analysis list
```

#### Capacity classification thresholds (prototype — not SAP standard)

| Classification | Condition |
|----------------|-----------|
| `NORMAL` | utilization < 90% |
| `WATCH` | 90% ≤ utilization < 100% |
| `HIGH` | 100% ≤ utilization < 110% |
| `CRITICAL` | utilization ≥ 110% |

#### Output schema (per work center)

```json
{
  "work_center": "WC-100",
  "description": "Assembly Line 1 — High-Precision",
  "available_hours": 40.0,
  "required_hours": 47.2,
  "utilization_pct": 118.0,
  "classification": "CRITICAL",
  "hour_deficit": 7.2,
  "contributing_orders": [
    {
      "order": "100045",
      "material": "FG-100",
      "scheduled_hours": 24.0,
      "priority": 1,
      "status": "RELEASED",
      "start_date": "2025-01-13",
      "finish_date": "2025-01-17"
    }
  ],
  "total_contributing_orders": 4
}
```

#### Error cases

| Condition | Response field |
|-----------|---------------|
| Specified WC not found | `"error": "Work center 'X' not found in simulated data."` |

---

### 4.3 Order Risk Scorer

**Function:** `order_risk_scorer(order_id: str | None = None) -> dict`

**Purpose:** Score each production order on five factors and assign HIGH / MEDIUM / LOW risk rating.

#### Input

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `order_id` | str \| None | No | Order number. If `None`, score all orders. |

#### Scoring algorithm (per order)

```
score_points = 0

Factor 1 — MATERIAL_SHORTAGE (3 pts per component with shortage)
  For each BOM component of order.material:
    required = order.qty × comp.required_qty
    available = inventory[comp].available_qty
    If required > available:
      score_points += 3
      Append MATERIAL_SHORTAGE factor with detail

Factor 2 — CAPACITY_OVERLOAD (2 pts if HIGH, 3 pts if CRITICAL)
  wc = WORK_CENTERS[order.work_center]
  pct = (wc.required_hours / wc.available_hours) × 100
  classification = classify(pct)
  If classification == "HIGH":   score_points += 2
  If classification == "CRITICAL": score_points += 3
  Append CAPACITY_OVERLOAD factor

Factor 3 — SUPPLIER_DELAY (2 pts per late PO)
  For each BOM component:
    For each OPEN PO for that component:
      days_late = max(0, PO.delivery_date - order.start_date)
      If days_late > 0:
        score_points += 2
        Append SUPPLIER_DELAY factor

Factor 4 — HIGH_PRIORITY_ORDER (1 pt if priority == 1)
  If order.priority == 1:
    score_points += 1
    Append HIGH_PRIORITY_ORDER factor (severity: INFO)

Rating:
  score_points >= 6 → HIGH
  score_points 3–5  → MEDIUM
  score_points < 3  → LOW
```

#### Expected scores for the scenario

| Order | Shortage pts | Capacity pts | Supplier pts | Priority pts | Total | Rating |
|-------|-------------|-------------|-------------|-------------|-------|--------|
| 100045 | 6 (RM-101 +3, RM-102 +3) | 3 (CRITICAL) | 2 (PO late) | 1 (P1) | **12** | 🔴 HIGH |
| 100046 | 3 (RM-104) | 3 (CRITICAL) | 2 (PO late) | 1 (P1) | **9** | 🔴 HIGH |
| 100047 | 0 | 3 (CRITICAL) | 0 | 0 | **3** | 🟡 MEDIUM |
| 100048 | 0 | 3 (CRITICAL) | 0 | 0 | **3** | 🟡 MEDIUM |
| 100049 | 3 (RM-103) | 0 (NORMAL) | 2 (PO late) | 0 | **5** | 🟡 MEDIUM |
| 100050 | 0 | 0 (NORMAL) | 0 | 0 | **0** | 🟢 LOW |

> Note: Order 100045 scores 12 because FG-100 BOM includes RM-102 (2 EA/parent × 1,000 qty = 2,000 EA required; only 800 EA available → shortage 1,200 EA adds another +3).

#### Output schema

```json
{
  "data_source": "SIMULATED",
  "skill": "OrderRiskScorer",
  "order_risk_analysis": [
    {
      "order": "100045",
      "material": "FG-100",
      "qty": 1000,
      "work_center": "WC-100",
      "status": "RELEASED",
      "priority": 1,
      "start_date": "2025-01-13",
      "finish_date": "2025-01-17",
      "risk_rating": "HIGH",
      "score_points": 9,
      "risk_factors": [
        { "factor": "MATERIAL_SHORTAGE", "severity": "HIGH", "detail": [ ... ] },
        { "factor": "CAPACITY_OVERLOAD", "severity": "CRITICAL", "detail": "WC-100 at 118.0% utilization (CRITICAL)." },
        { "factor": "SUPPLIER_DELAY", "severity": "HIGH", "detail": "PO 4500012345 for RM-101 is 4 day(s) late ..." },
        { "factor": "HIGH_PRIORITY_ORDER", "severity": "INFO", "detail": "Order has priority 1 — customer-facing impact." }
      ],
      "note": "..."
    }
  ],
  "summary": {
    "total_orders": 6,
    "high_risk": 2,
    "medium_risk": 3,
    "low_risk": 1
  }
}
```

Orders in response are **sorted by `score_points` descending**.

#### Error cases

| Condition | Response field |
|-----------|---------------|
| Specified order not found | `"error": "Order 'X' not found in simulated data."` |

---

### 4.4 Planner Recommendation

**Function:** `planner_recommendation(order_id: str) -> dict`

**Purpose:** Combine facts from MRP, Capacity, and Risk skills for a specific order. Generate a ranked list of corrective options. Flag items requiring manager approval. Identify tradeoff warnings. Always read-only — draft only.

#### Input

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `order_id` | str | Yes | Production order number |

#### Algorithm

```
1. Fetch order from PRODUCTION_ORDERS
   → If not found: return error, stop

2. Call mrp_exception_analyzer(order.material)   [internal]
3. Call capacity_analyzer(order.work_center)      [internal]
4. Call order_risk_scorer(order_id)               [internal]

5. Extract factor_types from risk analysis

6. Build options list:
   If SUPPLIER_DELAY in factors:
     → Add EXPEDITE_PO (rank 1, requires_manager_approval=True)
   
   If CAPACITY_OVERLOAD in factors:
     → Add MOVE_QTY_TO_ALT_WORK_CENTER (rank 2, requires_manager_approval=False)
       Expected effect includes WC-200 spare hours and utilization
     → Add AUTHORIZE_OVERTIME (rank 3, requires_manager_approval=True)
       Description includes hour_deficit from WC data

   Always add:
     → RESCHEDULE_ORDER (rank = len(options)+1)
       requires_manager_approval = (order.customer_order is not None)

7. Sort options by rank ascending
8. recommended_next_action = options[0]

9. Tradeoff warnings:
   If CAPACITY_OVERLOAD and order.priority == 1:
     Find lower-priority orders on same work center
     If any: append HIGH_PRIORITY_PROTECTION warning

10. Return ranked_options, recommended_next_action,
    tradeoff_warnings, read_only_notice
```

#### Option schema

Each option in `ranked_options`:

```json
{
  "rank": 1,
  "option": "EXPEDITE_PO",
  "description": "Contact vendor to request early delivery of open PO(s).",
  "expected_effect": "Closes material shortage; allows order to start on original date.",
  "constraints": "May incur expedite fees.",
  "requires_manager_approval": true,
  "approval_reason": "Expedite fees represent additional cost — requires manager approval.",
  "confidence": "HIGH",
  "data_basis": "PO delivery dates vs. order requirement dates from simulated purchase orders."
}
```

#### Manager approval rules

| Option | requires_manager_approval | Reason |
|--------|--------------------------|--------|
| EXPEDITE_PO | **Always true** | Expedite fees represent additional cost |
| MOVE_QTY_TO_ALT_WORK_CENTER | **Always false** | No cost or customer impact |
| AUTHORIZE_OVERTIME | **Always true** | Overtime cost and customer-committed schedule impact |
| RESCHEDULE_ORDER | **True if order has a customer_order** | Customer communication required |

#### Read-only notice (always present)

```
"This is a draft recommendation only. The agent cannot execute, reschedule,
release, or modify any SAP order or purchase order. All actions require
explicit planner (and where flagged, manager) approval."
```

#### Error cases

| Condition | Response field |
|-----------|---------------|
| Order not found | `"error": "Order 'X' not found in simulated data."` |

---

### 4.5 What-If Analysis

**Function:** `whatif_po_arrives_earlier(po_number: str, days_earlier: int) -> dict`

**Purpose:** Simulate the effect of a PO arriving `days_earlier` days before its current delivery date.

#### Input

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `po_number` | str | Yes | PO number, e.g. `"4500012345"` |
| `days_earlier` | int | Yes | Number of days to subtract from delivery date |

#### Algorithm

```
1. Find PO in PURCHASE_ORDERS
   → If not found: return error, stop

2. simulated_delivery_date = original_delivery_date - days_earlier days

3. Find all production orders where PO.material appears as a BOM component
   (i.e., any order whose finished good has PO.material in its BOM)

4. For each affected order:
   originally_late = max(0, original_delivery_date - order.start_date)
   simulated_late  = max(0, simulated_delivery_date - order.start_date)
   risk_resolved   = (simulated_late <= 0)

5. Return affected_orders, simulated_delivery_date, whatif_note
   Note always states: "No PO has been modified. Actual delivery date remains X."
```

#### Expected result for the scenario (PO 4500012345, 2 days earlier)

| Item | Value |
|------|-------|
| Original delivery | 2025-01-17 |
| Simulated delivery | **2025-01-15** |
| Order 100045 start | 2025-01-13 |
| Originally late | 4 days |
| Simulated late | **2 days** |
| Risk resolved | **No** (PO still 2 days late) |

---

## 5. Agent Specification

**File:** `agent/agent.py`  
**Class:** `ProductionPlanningAgent`

### 5.1 LLM configuration

| Setting | Value / Source |
|---------|---------------|
| Model | `gpt-4o` (default) or `PP_AGENT_MODEL` env var |
| Client | `openai.OpenAI` |
| Base URL | `AICORE_BASE_URL` env var (SAP AI Core proxy) |
| API key | `AICORE_API_KEY` env var |
| Tool choice | `"auto"` |
| Max iterations | 10 (infinite-loop guard) |

### 5.2 System prompt structure

The system prompt establishes:

1. **Persona** — Expert SAP PP analyst, analytical, precise, conservative.
2. **Data source** — All data is SIMULATED. Never invent data.
3. **Tool registry** — Names and brief descriptions of all 5 tools.
4. **Response format** — Separate RETRIEVED FACTS from ANALYSIS & RECOMMENDATIONS; use markdown; include risk badges; include summary table for multi-order results.
5. **Guardrails** (10 explicit rules) — See §8.
6. **Conversation memory** — Maintain order context across turns.
7. **Scenario context** — The Monday morning disruption facts as priming context.

### 5.3 Tool definitions registered with the LLM

| Tool name | Required params | Optional params |
|-----------|----------------|-----------------|
| `mrp_exception_analyzer` | `finished_good: str` | — |
| `capacity_analyzer` | — | `work_center_id: str` |
| `order_risk_scorer` | — | `order_id: str` |
| `planner_recommendation` | `order_id: str` | — |
| `whatif_po_arrives_earlier` | `po_number: str`, `days_earlier: int` | — |

### 5.4 Agentic loop

```
chat(user_message):
  1. Extract order number from user_message via regex \b(1\d{5})\b
     → If found, store as _last_order_context
  2. Append user message to history
  3. Loop up to 10 times:
     a. POST to LLM with full history + tools
     b. If finish_reason == "stop" or no tool_calls:
        → Return message.content
     c. For each tool_call in message.tool_calls:
        → Dispatch to Python skill function
        → Append tool result to history
  4. If loop exhausted: return fallback message
```

### 5.5 Conversation history format

```python
[
  {"role": "system",    "content": SYSTEM_PROMPT},
  {"role": "user",      "content": "Which orders are at risk?"},
  {"role": "assistant", "content": None, "tool_calls": [...]},
  {"role": "tool",      "tool_call_id": "...", "content": "{...json...}"},
  {"role": "assistant", "content": "## Retrieved Facts\n\n..."},
  ...
]
```

### 5.6 Session management

- `ProductionPlanningAgent.__init__()` — initializes history with system prompt.
- `ProductionPlanningAgent.chat(message)` — processes one turn, returns reply string.
- `ProductionPlanningAgent.reset()` — clears history, restores system prompt only.

---

## 6. API Specification

**File:** `agent/server.py`  
**Framework:** FastAPI  
**Base URL:** `http://localhost:8000` (development) / deployed CF URL (production)

### 6.1 CORS

CORS is enabled for all origins (`allow_origins=["*"]`), all methods, all headers. Suitable for prototype; restrict in production.

### 6.2 Endpoints

---

#### `GET /health`

Liveness check.

**Response `200 OK`:**
```json
{
  "status": "ok",
  "data_source": "SIMULATED",
  "scenario_date": "2025-01-13"
}
```

---

#### `GET /scenario`

Returns the full simulated dataset for UI display.

**Response `200 OK`:**
```json
{
  "data_source": "SIMULATED",
  "disclaimer": "All data is simulated for prototype purposes only.",
  "demand_context": {
    "scenario": "Monday morning disruption",
    "demand_increase_pct": 20,
    "fg100_customer_demand": 1200,
    "fg100_existing_stock_covering": 200,
    "fg100_production_order_qty": 1000,
    "reference_date": "2025-01-13",
    "note": "data_source: SIMULATED (prototype)"
  },
  "production_orders": [ ... ],
  "work_centers": [ ... ],
  "mrp_exceptions": [ ... ],
  "purchase_orders": [ ... ]
}
```

---

#### `POST /chat`

Send a user message and receive the agent's reply.

**Request body:**
```json
{
  "message": "Which production orders are at risk this week?",
  "session_id": "planner-session-1"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | str | Yes | — | The planner's message |
| `session_id` | str | No | `"default"` | Session identifier |

**Response `200 OK`:**
```json
{
  "reply": "## Retrieved Facts\n\n...",
  "session_id": "planner-session-1"
}
```

**Response `500 Internal Server Error`:**
```json
{
  "detail": "<error message>"
}
```

---

#### `POST /reset`

Clear conversation history for a session.

**Request body:**
```json
{
  "session_id": "planner-session-1"
}
```

**Response `200 OK`:**
```json
{
  "status": "reset",
  "session_id": "planner-session-1"
}
```

---

## 7. UI Specification

**Location:** `ui/src/`  
**Framework:** React 18, Vite  
**Dependencies:** `marked` (markdown rendering), `@ui5/webcomponents-react` (available but not required for core chat)  
**Build output:** `agent/static/` (served by FastAPI)

### 7.1 Layout structure

```
┌─────────────────────────────────────────────────────────┐
│  HEADER: logo | title | "SIMULATED DATA" | buttons      │
├─────────────────────────────────────────────────────────┤
│  SCENARIO PANEL (collapsible)                           │
│    stat cards | orders table | MRP table | WC table     │
├──────────────────────────────────┬──────────────────────┤
│  CHAT AREA                       │  SIDEBAR             │
│    messages list (scrollable)    │  Test questions      │
│    ──────────────────────────    │  Guardrails panel    │
│    input field | send button     │  Capacity thresholds │
├──────────────────────────────────┴──────────────────────┤
│  FOOTER: SIMULATED DATA disclaimer                      │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Components

#### `App` (root)

State:
- `messages: Array<{role, content, loading?}>` — conversation history for display
- `input: string` — current input field value
- `loading: boolean` — true while awaiting agent response
- `scenario: object | null` — scenario data from `GET /scenario`
- `showScenario: boolean` — toggle for scenario panel

On mount: fetch `/scenario` → set `scenario`.

#### `ScenarioPanel`

Props: `scenario: object`

Renders:
- **Stat cards** — demand spike %, MRP exception count, priority-1 order count, total order count
- **Production orders table** — all 6 orders with priority badge and status badge
- **MRP exceptions table** — material, exception text, dates, required/available/shortage quantities
- **Work center table** — WC ID, available hours, required hours, utilization %, `CapacityBadge`

#### `MessageBubble`

Props: `msg: {role, content, loading?}`

- `role === "user"` → right-aligned, SAP brand blue background
- `role === "agent"` → left-aligned, white card with shadow; content rendered via `marked.parse()` as `dangerouslySetInnerHTML`
- `loading === true` → show animated three-dot typing indicator

#### `RiskBadge`

Props: `rating: "HIGH" | "MEDIUM" | "LOW"`

| Rating | Background | Color | Emoji |
|--------|-----------|-------|-------|
| HIGH | `#fce8e8` | `#bb0000` | 🔴 |
| MEDIUM | `#fef3e2` | `#e76500` | 🟡 |
| LOW | `#e8f5e9` | `#256f3a` | 🟢 |

#### `CapacityBadge`

Props: `classification: "NORMAL" | "WATCH" | "HIGH" | "CRITICAL"`

| Classification | Background | Color |
|----------------|-----------|-------|
| CRITICAL | `#fce8e8` | `#bb0000` |
| HIGH | `#fef3e2` | `#e76500` |
| WATCH | `#fff8e1` | `#d47e00` |
| NORMAL | `#e8f5e9` | `#256f3a` |

### 7.3 Test questions (pre-wired)

Displayed as clickable buttons in the sidebar. On click, calls `sendMessage(question)`.

1. "Which production orders are at risk this week?"
2. "Why is order 100045 at risk?"
3. "What should I do?"
4. "What if PO 4500012345 arrives two days earlier?"
5. "Release order 100045 now."

### 7.4 Session constant

`SESSION_ID = "planner-session-1"` — fixed single-session constant (prototype).

### 7.5 API base URL

Resolved from `import.meta.env.VITE_API_URL` → falls back to `"http://localhost:8000"`.

In development, Vite proxies `/chat`, `/reset`, `/scenario`, `/health` to `http://localhost:8000`.

### 7.6 `sendMessage` flow

```
sendMessage(text):
  1. Append {role: "user", content: text} to messages
  2. Append {role: "agent", content: "", loading: true} to messages
  3. Set loading = true; clear input
  4. POST /chat {message: text, session_id}
  5. On success: replace last message with {role: "agent", content: data.reply}
  6. On error: replace last message with error markdown
  7. Set loading = false
```

### 7.7 Guardrails panel (sidebar)

Static list of 7 guardrails:
- Read-only: no SAP transactions executed
- Facts retrieved before every answer
- Recommendations separated from facts
- Manager approval flagged for cost/impact items
- HIGH-priority orders never de-prioritized silently
- Missing data reported, never estimated
- Confidence & data basis stated for all recommendations

### 7.8 Vite build configuration

```js
build: {
  outDir: '../agent/static',
  emptyOutDir: true,
}
```

---

## 8. Guardrail Implementation

Each guardrail is enforced at a specific layer. All guardrails are active in Version 1.

| ID | Guardrail | Enforcement layer | Implementation detail |
|----|-----------|------------------|-----------------------|
| GR-01 | Read-only — no SAP transactions | System prompt (rule 4) + agent logic | System prompt rule: "NEVER execute, release, reschedule, or modify any SAP order or PO." If asked to release/execute: decline and explain. |
| GR-02 | Facts first — retrieve before answering | LLM tool-calling flow | Agent calls skills via tool-calling. System prompt rule 2: "Retrieve facts through tools BEFORE answering." |
| GR-03 | Separate facts from recommendations | System prompt (rule 3) | "Separate retrieved facts from recommendations — never mix them." Response format: "RETRIEVED FACTS" section then "ANALYSIS & RECOMMENDATIONS". |
| GR-04 | Manager approval flagging | `planner_recommendation` skill output | `requires_manager_approval: true` with `approval_reason` on EXPEDITE_PO, AUTHORIZE_OVERTIME, RESCHEDULE_ORDER (when customer-committed). System prompt rule 6. |
| GR-05 | HIGH-priority protection | `planner_recommendation` tradeoff warnings | `tradeoff_warnings` list includes `HIGH_PRIORITY_PROTECTION` entry naming all lower-priority orders on same WC when order.priority == 1. System prompt rule 7. |
| GR-06 | Missing data reported, never estimated | All skills + system prompt | All skills have `data_missing`, `error`, `po_warning` fields. System prompt rule 1 and 9. |
| GR-07 | Confidence + data basis on every recommendation | `planner_recommendation` output fields | Each option has `confidence` ("HIGH"/"MEDIUM") and `data_basis` (string referencing specific simulated data). System prompt rule 8. |

---

## 9. Scoring & Classification Logic

### 9.1 Capacity classification

```python
def _classify_utilization(pct: float) -> str:
    if pct < 90.0:   return "NORMAL"
    if pct < 100.0:  return "WATCH"
    if pct < 110.0:  return "HIGH"
    return "CRITICAL"
```

> ⚠️ Prototype thresholds — not SAP standard.

### 9.2 Risk scoring weights

| Factor | Trigger condition | Points |
|--------|------------------|--------|
| MATERIAL_SHORTAGE | Any component shortage > 0 | +3 per component |
| CAPACITY_OVERLOAD (HIGH) | WC utilization 100–110% | +2 |
| CAPACITY_OVERLOAD (CRITICAL) | WC utilization > 110% | +3 |
| SUPPLIER_DELAY | Any open PO with delivery_date > order.start_date | +2 per late PO |
| HIGH_PRIORITY_ORDER | order.priority == 1 | +1 |
| MATERIAL_DATA_MISSING | No inventory record for a component | +2 |
| WORK_CENTER_DATA_MISSING | No WC record for order.work_center | +1 |

### 9.3 Risk rating thresholds

| Score | Rating |
|-------|--------|
| ≥ 6 | 🔴 HIGH |
| 3 – 5 | 🟡 MEDIUM |
| < 3 | 🟢 LOW |

### 9.4 Days-late calculation

```python
days_late = max(0, (delivery_date - requirement_date).days)
```

Where `requirement_date` = `order.start_date` for shortage scenarios.

---

## 10. Error Handling

### 10.1 Skill-level errors

All skill functions return error information **within the response dict** — they never raise exceptions. The LLM receives the error JSON and reports it to the planner in natural language.

Error response format:
```json
{ "error": "Descriptive message about what is missing." }
```

### 10.2 Agent-level errors

The `chat()` method wraps the LLM loop in a try/except. The FastAPI endpoint catches exceptions and returns HTTP 500 with `detail`.

### 10.3 LLM loop guard

Maximum 10 tool-call iterations per turn. If exceeded:
```
"I was unable to complete the analysis in the allowed number of steps. Please try a more specific question."
```

### 10.4 UI-level errors

If `POST /chat` returns a non-200 response or a network error, the UI renders an error message in an agent bubble:
```markdown
❌ **Error:** Could not reach the agent backend. Make sure the server is running.
`<error.message>`
```

---

## 11. File Structure

```
production-planning-risk-agent/
│
├── agent/                        # Python backend
│   ├── data.py                   # All simulated SAP-like data (SIMULATED label)
│   ├── skills.py                 # Four planning skills + what-if function
│   ├── agent.py                  # GPT-4o agent class with tool-calling
│   ├── server.py                 # FastAPI app — API routes
│   ├── main.py                   # Entry point — serves API + static UI
│   ├── requirements.txt          # Python dependencies
│   ├── Procfile                  # CF deployment: web: python main.py
│   ├── runtime.txt               # python-3.11.x
│   ├── .env.example              # Environment variable template
│   └── static/                   # Built React UI (generated by npm run build)
│       ├── index.html
│       └── assets/
│
├── ui/                           # React frontend
│   ├── src/
│   │   ├── main.jsx              # React entry point
│   │   ├── App.jsx               # Root component with all UI logic
│   │   ├── App.css               # Layout and component styles
│   │   └── index.css             # Global CSS variables and resets
│   ├── index.html                # Vite HTML template
│   ├── vite.config.js            # Build config — output to agent/static
│   └── package.json
│
├── intent.md                     # Intent document
├── requirements.md               # Requirements document
├── specification.md              # This document
├── README.md                     # Developer setup guide
├── mta.yaml                      # SAP BTP MTA deployment descriptor
└── package.json                  # Root npm scripts
```

---

## 12. Environment & Configuration

### 12.1 Required environment variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AICORE_BASE_URL` | SAP AI Core proxy base URL | `https://your-proxy.example.com/v1` |
| `AICORE_API_KEY` | API key for SAP AI Core | `sk-...` |

### 12.2 Optional environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PP_AGENT_MODEL` | `gpt-4o` | LLM model name |
| `PORT` | `8000` | Server listen port |

### 12.3 Development setup

```bash
# 1. Install Python dependencies
cd agent && pip install -r requirements.txt

# 2. Configure environment
cp agent/.env.example agent/.env
# Edit agent/.env with real credentials

# 3. Start agent backend (development)
cd agent && uvicorn server:app --reload --port 8000

# 4. Install UI dependencies
npm --prefix ui install

# 5. Start UI dev server (proxies API to localhost:8000)
npm --prefix ui run dev
# Open http://localhost:5173
```

### 12.4 Production build

```bash
# Build UI into agent/static/
npm --prefix ui run build

# Start the unified server (API + UI)
cd agent && python main.py
# Open http://localhost:8000
```

---

## 13. Deployment

### 13.1 SAP BTP Cloud Foundry

The application deploys as a single CF application from the `agent/` directory.

**`Procfile`:**
```
web: python main.py
```

**`runtime.txt`:**
```
python-3.11.x
```

**Build steps (before `cf push`):**
1. `npm --prefix ui run build` — builds React app into `agent/static/`
2. `pip install -r requirements.txt` — installs Python dependencies

**`mta.yaml` module:**
```yaml
- name: pp-risk-agent-backend
  type: python
  path: agent
  parameters:
    buildpack: python_buildpack
    memory: 512M
    disk-quota: 512M
  properties:
    PORT: 8080
```

### 13.2 Static file serving

`agent/main.py` mounts `agent/static/` as a `StaticFiles` app at `/` **after** all API routes are registered. API routes take precedence. Any path not matched by an API route is served from the static build.

```python
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

### 13.3 Environment variables on CF

Set via `cf set-env` or in the `manifest.yml`:
```
AICORE_BASE_URL=https://...
AICORE_API_KEY=...
PORT=8080
```

---

*All data is SIMULATED. This specification describes a prototype for demonstration purposes only.*
*No real SAP system is connected. No orders, materials, or purchase orders represent live data.*
