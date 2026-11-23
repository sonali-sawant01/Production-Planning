# Requirements — Production Planning Risk Agent

> **data_source: SIMULATED (prototype)** — No real SAP system is connected.
> All requirements reference simulated data only.

---

## 1. Functional Requirements

### 1.1 Simulated Data

| ID | Requirement |
|----|-------------|
| FR-D01 | The system SHALL provide a simulated Material master for each material referenced in production orders, containing: material number, plant, MRP type, lot size, safety stock, lead time in days, and unit of measure. |
| FR-D02 | The system SHALL provide a simulated Inventory record for each raw material, containing: material, plant, storage location, available quantity, and allocated quantity. |
| FR-D03 | The system SHALL provide a simulated Bill of Materials (BOM) for each finished good and semi-finished good, specifying parent material, component material, and required quantity per parent. |
| FR-D04 | The system SHALL provide at least six simulated Production Orders covering the following risk profiles: 2 HIGH-risk (combined material + capacity), 1 MEDIUM capacity-only, 1 MEDIUM material-only, 1 MEDIUM mixed, and 1 LOW (healthy). |
| FR-D05 | Each Production Order SHALL contain: order number, material, quantity, unit, start date, finish date, priority (1–3), work center, and status (RELEASED or PLANNED). |
| FR-D06 | The system SHALL provide simulated Work Center records for WC-100 and WC-200, each containing: available hours and required hours for the scenario week. |
| FR-D07 | WC-100 SHALL have required hours exceeding available hours by at least 10%, placing it in the CRITICAL classification. |
| FR-D08 | The system SHALL provide simulated Purchase Orders for each material with a shortage, each containing: PO number, material, quantity, delivery date, vendor, vendor name, and status. |
| FR-D09 | PO 4500012345 (RM-101) SHALL have a delivery date after the start date of order 100045, making it late by at least 1 day. |
| FR-D10 | The system SHALL provide simulated MRP Exception records for each material in shortage, containing: material, plant, exception code, exception text, requirement date, requirement quantity, available quantity, and shortage quantity. |
| FR-D11 | All simulated data records SHALL carry the label `data_source: SIMULATED` and a scenario reference date of 2025-01-13. |

---

### 1.2 Skill — MRP Exception Analyzer

| ID | Requirement |
|----|-------------|
| FR-M01 | The skill SHALL accept a finished good material number as input. |
| FR-M02 | The skill SHALL retrieve the material master record for the given finished good before producing any output. |
| FR-M03 | The skill SHALL explode the BOM one level and return all component materials and their required quantities per parent. |
| FR-M04 | For each component, the skill SHALL retrieve the inventory record and compute: total required quantity (order quantity × component quantity per parent), available quantity, and shortage quantity (max(0, required − available)). |
| FR-M05 | For each component with a shortage, the skill SHALL retrieve all open purchase orders for that component. |
| FR-M06 | For each late PO, the skill SHALL compute days late = delivery date − order start date, and include: PO number, delivery date, requirement date, days late, and PO quantity. |
| FR-M07 | The skill SHALL return retrieved facts only — no recommendations, no estimates. |
| FR-M08 | If no inventory record exists for a component, the skill SHALL report exactly which data is missing and SHALL NOT estimate a value. |
| FR-M09 | If no BOM exists for the given material, the skill SHALL report that no BOM was found. |

---

### 1.3 Skill — Capacity Analyzer

| ID | Requirement |
|----|-------------|
| FR-C01 | The skill SHALL accept an optional work center ID. If omitted, it SHALL analyze all work centers. |
| FR-C02 | The skill SHALL compute utilization as: `utilization (%) = required hours ÷ available hours × 100`. |
| FR-C03 | The skill SHALL classify each work center using the following prototype thresholds (not SAP standard): NORMAL < 90%; WATCH 90–100%; HIGH 100–110%; CRITICAL > 110%. |
| FR-C04 | The skill SHALL include the classification thresholds and the prototype disclaimer in every response. |
| FR-C05 | The skill SHALL list all production orders scheduled on the analyzed work center(s), including: order number, material, scheduled hours, priority, status, start date, and finish date. |
| FR-C06 | The skill SHALL compute and return the hour deficit (required − available, floored at 0) for each overloaded work center. |
| FR-C07 | If a specified work center ID does not exist in simulated data, the skill SHALL report exactly which work center is missing. |

---

### 1.4 Skill — Order Risk Scorer

| ID | Requirement |
|----|-------------|
| FR-R01 | The skill SHALL accept an optional order ID. If omitted, it SHALL score all production orders. |
| FR-R02 | The skill SHALL score each order on five factors: (1) material shortage, (2) capacity overload at the assigned work center, (3) order lateness, (4) supplier delay (late open PO), (5) order priority. |
| FR-R03 | The skill SHALL assign a risk rating of HIGH, MEDIUM, or LOW based on the accumulated factor score. |
| FR-R04 | Orders with score ≥ 6 points SHALL be rated HIGH; score 3–5 SHALL be rated MEDIUM; score < 3 SHALL be rated LOW. |
| FR-R05 | Each scored order SHALL include explicit evidence for every risk factor identified, including: factor name, severity, and detail. |
| FR-R06 | The skill SHALL return a summary count of HIGH, MEDIUM, and LOW orders alongside the per-order detail. |
| FR-R07 | The skill SHALL sort orders by score descending so the highest-risk orders appear first. |
| FR-R08 | If a specified order ID does not exist in simulated data, the skill SHALL report exactly which order is missing. |

---

### 1.5 Skill — Planner Recommendation

| ID | Requirement |
|----|-------------|
| FR-P01 | The skill SHALL accept a production order ID and SHALL retrieve facts from MRP Exception Analyzer, Capacity Analyzer, and Order Risk Scorer before producing any recommendation. |
| FR-P02 | The skill SHALL generate a ranked list of corrective options. The minimum options to evaluate are: (1) Expedite PO, (2) Move quantity to alternate work center (WC-200), (3) Authorize overtime, (4) Reschedule order. |
| FR-P03 | Each option SHALL include: rank, option name, description, expected effect, constraints, whether manager approval is required, the reason for manager approval (if applicable), confidence level, and data basis. |
| FR-P04 | The skill SHALL designate one option as the recommended next action. |
| FR-P05 | Recommendations involving expedite fees SHALL be flagged `requires_manager_approval: true` with reason "expedite fees represent additional cost". |
| FR-P06 | Recommendations involving overtime SHALL be flagged `requires_manager_approval: true` with reason "overtime cost and customer-committed schedule impact". |
| FR-P07 | Recommendations involving a change to a customer-committed delivery date SHALL be flagged `requires_manager_approval: true` with reason "customer communication required". |
| FR-P08 | If the order being analyzed is priority 1 and other lower-priority orders share the same work center, the skill SHALL include a tradeoff warning explicitly naming those lower-priority orders. |
| FR-P09 | Every response SHALL include a read-only notice stating that no SAP transaction has been executed and all actions require planner (and where flagged, manager) approval. |
| FR-P10 | If the order ID does not exist in simulated data, the skill SHALL report exactly which order is missing. |

---

### 1.6 What-If Analysis

| ID | Requirement |
|----|-------------|
| FR-W01 | The system SHALL provide a what-if function that accepts a PO number and a number of days earlier as inputs. |
| FR-W02 | The function SHALL compute the simulated delivery date = original delivery date − days earlier. |
| FR-W03 | For each production order that requires the PO's material (via BOM), the function SHALL compute: original days late, simulated days late, and whether the risk would be resolved (simulated days late ≤ 0). |
| FR-W04 | The function SHALL state clearly that no PO has been modified and the actual delivery date remains unchanged. |
| FR-W05 | If the specified PO number does not exist in simulated data, the function SHALL report exactly which PO is missing. |

---

### 1.7 Agent Behavior

| ID | Requirement |
|----|-------------|
| FR-A01 | The agent SHALL retrieve data through the appropriate skill(s) before answering any factual question about orders, materials, capacity, or recommendations. |
| FR-A02 | The agent SHALL maintain conversational memory within a session, so follow-up questions referencing a previously discussed order are resolved to that order automatically. |
| FR-A03 | Every agent response SHALL clearly separate the "RETRIEVED FACTS" section from the "ANALYSIS & RECOMMENDATIONS" section. |
| FR-A04 | The agent SHALL present production order risk results in a summary table with risk badges: 🔴 HIGH, 🟡 MEDIUM, 🟢 LOW. |
| FR-A05 | When asked to release, execute, reschedule, or modify any SAP order or purchase order, the agent SHALL decline, explain that it is read-only, and direct the planner to perform the action in SAP directly. |
| FR-A06 | The agent SHALL never invent, estimate, or extrapolate data values. If data is missing, it SHALL state exactly which data item is missing and stop. |
| FR-A07 | The agent SHALL flag every recommendation that requires manager approval using the label "⚠️ Requires manager approval" and SHALL state the reason. |
| FR-A08 | The agent SHALL never recommend de-prioritizing a HIGH-priority customer order to protect a lower-priority order without explicitly stating the trade-off in the response. |
| FR-A09 | Every recommendation SHALL include a confidence level (HIGH / MEDIUM / LOW) and the specific simulated data it is based on. |
| FR-A10 | The agent SHALL state `data_source: SIMULATED (prototype)` on every response that includes retrieved facts or recommendations. |

---

### 1.8 API (Backend)

| ID | Requirement |
|----|-------------|
| FR-API01 | The backend SHALL expose `POST /chat` accepting `{ message: string, session_id: string }` and returning `{ reply: string, session_id: string }`. |
| FR-API02 | The backend SHALL expose `POST /reset` accepting `{ session_id: string }` to clear conversation history for that session. |
| FR-API03 | The backend SHALL expose `GET /scenario` returning the full simulated dataset (demand context, production orders, work centers, MRP exceptions, purchase orders). |
| FR-API04 | The backend SHALL expose `GET /health` returning `{ status, data_source, scenario_date }`. |
| FR-API05 | The backend SHALL enable CORS for all origins to support browser-based UI access during prototyping. |
| FR-API06 | Each session SHALL maintain its own independent conversation history. |

---

### 1.9 UI (Chat Interface)

| ID | Requirement |
|----|-------------|
| FR-UI01 | The UI SHALL provide a chat interface with an input field, a send button, and a scrollable message history. |
| FR-UI02 | User messages SHALL be visually distinguished from agent responses (e.g., alignment, color). |
| FR-UI03 | Agent responses SHALL render markdown formatting including headings, bold, tables, lists, and code blocks. |
| FR-UI04 | The UI SHALL display a typing indicator while the agent is processing a request. |
| FR-UI05 | The UI SHALL provide at least five pre-wired test question buttons that send the question directly to the agent on click. |
| FR-UI06 | The UI SHALL include a collapsible scenario data panel showing: production orders table, MRP exceptions table, and work center capacity table. |
| FR-UI07 | The work center capacity table SHALL display utilization percentage and a color-coded classification badge (NORMAL / WATCH / HIGH / CRITICAL). |
| FR-UI08 | The UI SHALL display a persistent "SIMULATED DATA" label in the header and footer to make clear no real SAP data is shown. |
| FR-UI09 | The UI SHALL display an active guardrails panel listing all enforced behavioral guardrails. |
| FR-UI10 | The UI SHALL provide a "New Session" button that resets the conversation history. |
| FR-UI11 | The UI SHALL automatically scroll to the latest message after each response. |
| FR-UI12 | Input SHALL be disabled while the agent is processing to prevent duplicate submissions. |

---

## 2. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | **Response time**: The agent SHALL return a response within 30 seconds for any single-skill query under normal network conditions. |
| NFR-02 | **Accuracy**: The agent SHALL never return a risk rating that contradicts the data returned by the skills for the same order in the same session. |
| NFR-03 | **Consistency**: The agent SHALL produce the same risk ratings for the same order when queried multiple times within a session (deterministic skill output). |
| NFR-04 | **Usability**: All risk ratings SHALL be visually distinguishable using both color and emoji/icon (not color alone) to support accessibility. |
| NFR-05 | **Prototype labeling**: Every screen, response, and data record SHALL clearly indicate simulated/prototype status. No element SHALL present simulated data as live SAP data. |
| NFR-06 | **Read-only enforcement**: The system SHALL contain no code path that writes to, releases, or modifies any external system. |
| NFR-07 | **Session isolation**: Conversation history for one session SHALL NOT be visible to or affect another session. |
| NFR-08 | **Stateless data**: The simulated data layer SHALL be read-only in-memory Python structures. No database is required for the prototype. |
| NFR-09 | **Deployability**: The application SHALL be deployable to SAP BTP Cloud Foundry as a single Python process serving both the API and the built React UI. |
| NFR-10 | **Browser compatibility**: The UI SHALL work in current versions of Chrome, Edge, and Firefox without plugins. |

---

## 3. Guardrail Requirements

| ID | Guardrail | Enforcement point |
|----|-----------|-------------------|
| GR-01 | Agent is read-only — no SAP transactions executed | System prompt + explicit decline logic in agent |
| GR-02 | Facts retrieved through skills before every answer | Tool-calling flow; agent must call a skill before answering factual questions |
| GR-03 | Retrieved facts and recommendations are always separated | System prompt instruction + response format |
| GR-04 | Expedite fees, overtime, and customer date changes flagged for manager approval | `requires_manager_approval` field in `planner_recommendation` skill |
| GR-05 | HIGH-priority customer orders never de-prioritized silently | Tradeoff warning logic in `planner_recommendation` skill |
| GR-06 | Missing or inconsistent data reported, never estimated | Explicit `data_missing` / `error` fields in all skills; system prompt instruction |
| GR-07 | Every recommendation includes confidence level and data basis | Required fields in `planner_recommendation` skill output; system prompt instruction |

---

## 4. Test Acceptance Criteria

| # | Test Question | Pass Criteria |
|---|---------------|---------------|
| T-01 | "Which production orders are at risk this week?" | Returns a table of all 6 orders with correct risk ratings: 100045 HIGH, 100046 HIGH, 100047 MEDIUM, 100048 MEDIUM, 100049 MEDIUM, 100050 LOW. |
| T-02 | "Why is order 100045 at risk?" | Identifies RM-101 shortage (220 EA), WC-100 at 118% (CRITICAL), and PO 4500012345 as 4 days late. Separates facts from analysis. States data_source: SIMULATED. |
| T-03 | "What should I do?" (after T-02) | Applies recommendation to order 100045 using conversational context. Returns ranked options. Flags expedite PO and overtime as requiring manager approval. States confidence and data basis for each option. |
| T-04 | "What if PO 4500012345 arrives two days earlier?" | Computes simulated delivery date as 2025-01-15. Reports order 100045 would still be 2 days late (not resolved). States no PO has been modified. |
| T-05 | "Release order 100045 now." | Declines to execute. States agent is read-only. Directs planner to perform the action in SAP. Does NOT call any skill or simulate a release. |

---

## 5. Out of Scope (Version 1)

- Connection to a real SAP S/4HANA or ECC system
- Write-back, order release, or PO modification of any kind
- Multi-plant or multi-company-code scenarios
- User authentication or role-based access control
- Persistent storage or audit logging of recommendations
- Real-time MRP run triggers
- Mobile or native application
- Manager approval workflow (flagging only — no real workflow engine)
