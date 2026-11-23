"""
Simulated SAP-like manufacturing data for the Production Planning Risk Agent.
data_source: SIMULATED (prototype) — not connected to a real SAP system.

Scenario: Monday morning disruption
  - Customer demand +20%; FG-100 demand 1,200 EA
  - RM-101: 780 EA available vs 1,000 EA required → shortage 220 EA
  - WC-100: 40 hr available vs 47.2 hr required → 118% utilization (CRITICAL)
  - Order 100045 (FG-100) on WC-100; PO 4500012345 (RM-101) due after requirement date
"""

DATA_SOURCE = "SIMULATED"
SCENARIO_DATE = "2025-01-13"   # Monday morning reference date

# ---------------------------------------------------------------------------
# MATERIALS
# ---------------------------------------------------------------------------
MATERIALS = {
    "FG-100": {
        "material": "FG-100",
        "description": "Finished Good 100 — Customer Assembly A",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "EX",
        "safety_stock": 100,
        "lead_time_days": 5,
        "unit": "EA",
    },
    "FG-200": {
        "material": "FG-200",
        "description": "Finished Good 200 — Customer Assembly B",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "EX",
        "safety_stock": 50,
        "lead_time_days": 4,
        "unit": "EA",
    },
    "SFG-010": {
        "material": "SFG-010",
        "description": "Semi-Finished Good 010 — Sub-Assembly",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "EX",
        "safety_stock": 0,
        "lead_time_days": 3,
        "unit": "EA",
    },
    "FG-300": {
        "material": "FG-300",
        "description": "Finished Good 300 — Internal Component Set",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "EX",
        "safety_stock": 30,
        "lead_time_days": 3,
        "unit": "EA",
    },
    "FG-400": {
        "material": "FG-400",
        "description": "Finished Good 400 — Accessory Kit",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "EX",
        "safety_stock": 20,
        "lead_time_days": 4,
        "unit": "EA",
    },
    "FG-500": {
        "material": "FG-500",
        "description": "Finished Good 500 — Standard Kit",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "EX",
        "safety_stock": 10,
        "lead_time_days": 2,
        "unit": "EA",
    },
    "RM-101": {
        "material": "RM-101",
        "description": "Raw Material 101 — Precision Housing",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "FX",
        "safety_stock": 100,
        "lead_time_days": 7,
        "unit": "EA",
    },
    "RM-102": {
        "material": "RM-102",
        "description": "Raw Material 102 — Standard Bracket",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "FX",
        "safety_stock": 50,
        "lead_time_days": 3,
        "unit": "EA",
    },
    "RM-103": {
        "material": "RM-103",
        "description": "Raw Material 103 — Connector Assembly",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "FX",
        "safety_stock": 50,
        "lead_time_days": 5,
        "unit": "EA",
    },
    "RM-104": {
        "material": "RM-104",
        "description": "Raw Material 104 — Drive Shaft",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "FX",
        "safety_stock": 100,
        "lead_time_days": 6,
        "unit": "EA",
    },
    "RM-105": {
        "material": "RM-105",
        "description": "Raw Material 105 — Fastener Set",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "FX",
        "safety_stock": 200,
        "lead_time_days": 2,
        "unit": "EA",
    },
    "RM-106": {
        "material": "RM-106",
        "description": "Raw Material 106 — Packing Material",
        "plant": "1000",
        "mrp_type": "PD",
        "lot_size": "FX",
        "safety_stock": 100,
        "lead_time_days": 1,
        "unit": "EA",
    },
}

# ---------------------------------------------------------------------------
# INVENTORY  (key: (material, plant))
# ---------------------------------------------------------------------------
INVENTORY = {
    ("RM-101", "1000"): {
        "material": "RM-101", "plant": "1000",
        "storage_location": "0001",
        "available_qty": 780,   # <-- shortage scenario: needs 1,000
        "allocated_qty": 780,
        "unit": "EA",
    },
    ("RM-102", "1000"): {
        "material": "RM-102", "plant": "1000",
        "storage_location": "0001",
        "available_qty": 800,
        "allocated_qty": 500,
        "unit": "EA",
    },
    ("RM-103", "1000"): {
        "material": "RM-103", "plant": "1000",
        "storage_location": "0001",
        "available_qty": 150,   # <-- shortage scenario: needs 300
        "allocated_qty": 150,
        "unit": "EA",
    },
    ("RM-104", "1000"): {
        "material": "RM-104", "plant": "1000",
        "storage_location": "0001",
        "available_qty": 1450,  # <-- shortage scenario: FG-200 order needs 1,600
        "allocated_qty": 1450,
        "unit": "EA",
    },
    ("RM-105", "1000"): {
        "material": "RM-105", "plant": "1000",
        "storage_location": "0001",
        "available_qty": 1000,
        "allocated_qty": 900,
        "unit": "EA",
    },
    ("RM-106", "1000"): {
        "material": "RM-106", "plant": "1000",
        "storage_location": "0001",
        "available_qty": 500,
        "allocated_qty": 500,
        "unit": "EA",
    },
}

# ---------------------------------------------------------------------------
# BILL OF MATERIALS (BOM)
# ---------------------------------------------------------------------------
BOM = [
    # FG-100: Precision Housing + 2× Bracket
    {"parent": "FG-100", "component": "RM-101", "required_qty": 1, "unit": "EA"},
    {"parent": "FG-100", "component": "RM-102", "required_qty": 2, "unit": "EA"},

    # FG-200: 2× Drive Shaft
    {"parent": "FG-200", "component": "RM-104", "required_qty": 2, "unit": "EA"},

    # SFG-010: Bracket + Fastener Set
    {"parent": "SFG-010", "component": "RM-102", "required_qty": 1, "unit": "EA"},
    {"parent": "SFG-010", "component": "RM-105", "required_qty": 1, "unit": "EA"},

    # FG-300: Fastener Set + Packing
    {"parent": "FG-300", "component": "RM-105", "required_qty": 1, "unit": "EA"},
    {"parent": "FG-300", "component": "RM-106", "required_qty": 1, "unit": "EA"},

    # FG-400: Connector Assembly (shortage scenario)
    {"parent": "FG-400", "component": "RM-103", "required_qty": 1, "unit": "EA"},

    # FG-500: Fastener Set + Packing (healthy)
    {"parent": "FG-500", "component": "RM-105", "required_qty": 2, "unit": "EA"},
    {"parent": "FG-500", "component": "RM-106", "required_qty": 1, "unit": "EA"},
]

# ---------------------------------------------------------------------------
# WORK CENTERS
# ---------------------------------------------------------------------------
WORK_CENTERS = {
    "WC-100": {
        "work_center": "WC-100",
        "description": "Assembly Line 1 — High-Precision",
        "plant": "1000",
        "available_hours": 40.0,   # standard 40-hr week
        "required_hours": 47.2,    # 118% → CRITICAL
        "unit": "HR",
    },
    "WC-200": {
        "work_center": "WC-200",
        "description": "Assembly Line 2 — General",
        "plant": "1000",
        "available_hours": 32.0,
        "required_hours": 22.0,    # 68.75% → NORMAL
        "unit": "HR",
    },
}

# ---------------------------------------------------------------------------
# PRODUCTION ORDERS
# ---------------------------------------------------------------------------
PRODUCTION_ORDERS = [
    {
        "order": "100045",
        "material": "FG-100",
        "qty": 1000,
        "unit": "EA",
        "start_date": "2025-01-13",
        "finish_date": "2025-01-17",
        "priority": 1,
        "work_center": "WC-100",
        "status": "RELEASED",
        "scheduled_hours": 24.0,
        "customer_order": "SO-88123",
        "note": "Customer demand +20%; demand = 1,200 EA, existing stock covers 200 EA",
    },
    {
        "order": "100046",
        "material": "FG-200",
        "qty": 800,
        "unit": "EA",
        "start_date": "2025-01-13",
        "finish_date": "2025-01-16",
        "priority": 1,
        "work_center": "WC-100",
        "status": "RELEASED",
        "scheduled_hours": 16.0,
        "customer_order": "SO-88124",
        "note": "High-priority customer order; needs RM-104 (shortage 150 EA, PO delayed 3 days)",
    },
    {
        "order": "100047",
        "material": "SFG-010",
        "qty": 500,
        "unit": "EA",
        "start_date": "2025-01-14",
        "finish_date": "2025-01-18",
        "priority": 2,
        "work_center": "WC-100",
        "status": "PLANNED",
        "scheduled_hours": 4.0,
        "customer_order": None,
        "note": "Medium-priority sub-assembly; materials OK, affected by WC-100 queue",
    },
    {
        "order": "100048",
        "material": "FG-300",
        "qty": 300,
        "unit": "EA",
        "start_date": "2025-01-13",
        "finish_date": "2025-01-16",
        "priority": 3,
        "work_center": "WC-100",
        "status": "RELEASED",
        "scheduled_hours": 3.2,
        "customer_order": None,
        "note": "Low-priority; all materials available; at risk only due to WC-100 overload",
    },
    {
        "order": "100049",
        "material": "FG-400",
        "qty": 300,
        "unit": "EA",
        "start_date": "2025-01-14",
        "finish_date": "2025-01-20",
        "priority": 2,
        "work_center": "WC-200",
        "status": "PLANNED",
        "scheduled_hours": 12.0,
        "customer_order": None,
        "note": "WC-200 capacity is fine; risk is RM-103 shortage (150 EA short, PO 4 days late)",
    },
    {
        "order": "100050",
        "material": "FG-500",
        "qty": 200,
        "unit": "EA",
        "start_date": "2025-01-15",
        "finish_date": "2025-01-20",
        "priority": 3,
        "work_center": "WC-200",
        "status": "PLANNED",
        "scheduled_hours": 10.0,
        "customer_order": None,
        "note": "Healthy order — all materials available, WC-200 has spare capacity",
    },
]

# ---------------------------------------------------------------------------
# PURCHASE ORDERS
# ---------------------------------------------------------------------------
PURCHASE_ORDERS = [
    {
        "po": "4500012345",
        "material": "RM-101",
        "qty": 300,
        "unit": "EA",
        "delivery_date": "2025-01-17",   # order needs RM-101 by 2025-01-13 → 4 days late
        "vendor": "VENDOR-PREC-01",
        "vendor_name": "Precision Parts GmbH",
        "status": "OPEN",
        "note": "Late by 4 days vs requirement date 2025-01-13 for order 100045",
    },
    {
        "po": "4500012346",
        "material": "RM-104",
        "qty": 300,
        "unit": "EA",
        "delivery_date": "2025-01-17",   # order needs RM-104 by 2025-01-14 → 3 days late
        "vendor": "VENDOR-DRIVE-02",
        "vendor_name": "Drive Components Ltd",
        "status": "OPEN",
        "note": "Late by 3 days vs requirement date 2025-01-14 for order 100046",
    },
    {
        "po": "4500012347",
        "material": "RM-103",
        "qty": 200,
        "unit": "EA",
        "delivery_date": "2025-01-18",   # order needs RM-103 by 2025-01-14 → 4 days late
        "vendor": "VENDOR-CONN-03",
        "vendor_name": "Connector Systems Inc",
        "status": "OPEN",
        "note": "Late by 4 days vs requirement date 2025-01-14 for order 100049",
    },
]

# ---------------------------------------------------------------------------
# MRP EXCEPTIONS
# ---------------------------------------------------------------------------
MRP_EXCEPTIONS = [
    {
        "material": "RM-101",
        "plant": "1000",
        "exception_code": "02",
        "exception_text": "Stock below safety stock / material shortage",
        "requirement_date": "2025-01-13",
        "requirement_qty": 1000,
        "available_qty": 780,
        "shortage_qty": 220,
        "unit": "EA",
        "open_po": "4500012345",
        "note": "Critical: order 100045 starts today and cannot proceed without RM-101",
    },
    {
        "material": "RM-104",
        "plant": "1000",
        "exception_code": "02",
        "exception_text": "Stock below safety stock / material shortage",
        "requirement_date": "2025-01-14",
        "requirement_qty": 1600,
        "available_qty": 1450,
        "shortage_qty": 150,
        "unit": "EA",
        "open_po": "4500012346",
        "note": "Order 100046 (FG-200, 800 EA) requires 1,600 RM-104; only 1,450 available",
    },
    {
        "material": "RM-103",
        "plant": "1000",
        "exception_code": "02",
        "exception_text": "Stock below safety stock / material shortage",
        "requirement_date": "2025-01-14",
        "requirement_qty": 300,
        "available_qty": 150,
        "shortage_qty": 150,
        "unit": "EA",
        "open_po": "4500012347",
        "note": "Order 100049 (FG-400, 300 EA) requires 300 RM-103; only 150 available",
    },
]

# ---------------------------------------------------------------------------
# Demand context (for scenario narrative)
# ---------------------------------------------------------------------------
DEMAND_CONTEXT = {
    "scenario": "Monday morning disruption",
    "demand_increase_pct": 20,
    "fg100_customer_demand": 1200,
    "fg100_existing_stock_covering": 200,
    "fg100_production_order_qty": 1000,
    "reference_date": "2025-01-13",
    "note": "data_source: SIMULATED (prototype)",
}
