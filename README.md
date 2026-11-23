# Production Planning Risk Agent

> **data_source: SIMULATED (prototype)** — No real SAP system is connected. All data is simulated for demonstration purposes.

An AI-powered agent for SAP PP planners that analyzes production order risk using simulated, SAP-like manufacturing data.

---

## Architecture

```
ui/                   React + SAP UI5 Web Components chat interface
agent/
  data.py             All simulated manufacturing data (SIMULATED label)
  skills.py           Four planning skills (MRP, Capacity, Risk, Recommendation)
  agent.py            GPT-4o agent with tool-calling, conversational memory
  server.py           FastAPI REST API (POST /chat, POST /reset, GET /scenario)
  main.py             Entry point; serves API + built React static files
```

## Scenario — Monday Morning Disruption

| Item | Detail |
|------|--------|
| Customer demand | +20% spike |
| FG-100 demand | 1,200 EA (order: 1,000 EA + 200 EA stock) |
| RM-101 (Precision Housing) | 780 EA available vs. 1,000 EA required → **shortage 220 EA** |
| WC-100 (Assembly Line 1) | 40 hr available vs. 47.2 hr required → **118% utilization (CRITICAL)** |
| PO 4500012345 | RM-101 delivery 2025-01-17 — **4 days after** order 100045 start date |

## Six Production Orders

| Order | Material | Risk | Reason |
|-------|----------|------|--------|
| 100045 | FG-100 | 🔴 HIGH | Material shortage (RM-101) + capacity overload (WC-100) + late PO |
| 100046 | FG-200 | 🔴 HIGH | Material shortage (RM-104) + late PO |
| 100047 | SFG-010 | 🟡 MEDIUM | WC-100 capacity overload |
| 100048 | FG-300 | 🟡 MEDIUM | WC-100 capacity overload only |
| 100049 | FG-400 | 🟡 MEDIUM | RM-103 shortage + late PO (WC-200 is fine) |
| 100050 | FG-500 | 🟢 LOW | All materials available, WC-200 has spare capacity |

## Four Skills

1. **MRP Exception Analyzer** — Traces finished good → BOM → component shortages → open POs
2. **Capacity Analyzer** — Utilization = required ÷ available × 100; classifies NORMAL/WATCH/HIGH/CRITICAL
3. **Order Risk Scorer** — Rates each order HIGH/MEDIUM/LOW with multi-factor evidence
4. **Planner Recommendation** — Ranked options (expedite PO, move to WC-200, overtime, reschedule) + one recommended action

## Guardrails

- ✅ **Read-only**: never executes any SAP transaction
- ✅ **Facts first**: always retrieves data through skills before answering
- ✅ **Separation**: retrieved facts clearly separated from recommendations
- ✅ **Manager approval**: flagged for expedite fees, overtime, customer date changes
- ✅ **Priority protection**: HIGH-priority customer orders never de-prioritized silently
- ✅ **Missing data**: reported exactly, never estimated
- ✅ **Confidence**: every recommendation includes confidence level and data basis

---

## Running Locally with Your Own OpenAI API Key

> You do **not** need SAP AI Core to run and test the full agent locally.
> The agent uses the standard OpenAI Python SDK, which works directly with
> an OpenAI API key (platform.openai.com) or any OpenAI-compatible endpoint
> (Azure OpenAI, local Ollama, LM Studio, etc.).

### Option A — Standard OpenAI API key (simplest)

**1. Install dependencies**

```bash
cd agent
pip install -r requirements.txt
```

**2. Create your `.env` file**

```bash
cp .env.example .env
```

Open `agent/.env` and set:

```env
# Your OpenAI API key from https://platform.openai.com/api-keys
AICORE_API_KEY=sk-...your-key-here...

# Leave base URL empty to use the standard OpenAI API
AICORE_BASE_URL=

# Model to use (gpt-4o recommended; gpt-4o-mini works and is cheaper)
PP_AGENT_MODEL=gpt-4o
```

**3. Start the backend**

```bash
# From the agent/ directory:
uvicorn server:app --reload --port 8000
```

**4. Start the React UI**

```bash
# From the project root (new terminal):
npm --prefix ui run dev
# Opens at http://localhost:5173
```

**5. Test it**

Open `http://localhost:5173` and click:
> *"Which production orders are at risk this week?"*

---

### Option B — Azure OpenAI

```env
AICORE_BASE_URL=https://<your-resource>.openai.azure.com/openai/deployments/<deployment-name>
AICORE_API_KEY=<your-azure-api-key>
PP_AGENT_MODEL=gpt-4o
```

---

### Option C — Local model (Ollama / LM Studio)

Point `AICORE_BASE_URL` at your local server's OpenAI-compatible endpoint and set a model that supports function-calling (tool use):

```env
# Ollama example:
AICORE_BASE_URL=http://localhost:11434/v1
AICORE_API_KEY=ollama
PP_AGENT_MODEL=llama3.1:8b-instruct

# LM Studio example:
AICORE_BASE_URL=http://localhost:1234/v1
AICORE_API_KEY=lm-studio
PP_AGENT_MODEL=mistral-7b-instruct
```

> ⚠️ Local models vary in function-calling quality. `llama3.1`, `mistral-nemo`,
> and `qwen2.5` are known to work well. If the agent stops calling tools,
> switch to a model with stronger tool-use support or use `gpt-4o-mini` via OpenAI.

---

### Option D — SAP AI Core (production)

```env
AICORE_BASE_URL=https://api.ai.<region>.aws.ml.hana.ondemand.com/v2
AICORE_API_KEY=<bearer-token>   # static token for quick testing only
PP_AGENT_MODEL=gpt-4o
```

For production use with automatic token refresh, see [`DEPLOYMENT.md`](DEPLOYMENT.md) §4.

---

### Environment variable reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AICORE_API_KEY` | Yes | — | OpenAI API key, Azure key, or AI Core bearer token |
| `AICORE_BASE_URL` | No | *(OpenAI default)* | Custom API base URL; leave empty for standard OpenAI |
| `PP_AGENT_MODEL` | No | `gpt-4o` | Model name passed to the LLM |
| `PORT` | No | `8000` | Server port |

> When `AICORE_BASE_URL` is empty, the OpenAI SDK connects to `https://api.openai.com/v1` automatically.

---

## Running (Full Build — UI bundled into agent)

```bash
# 1. Build the React UI into agent/static/
npm --prefix ui run build

# 2. Start the unified server (API + UI on one port)
cd agent && python main.py

# 3. Open in browser
# http://localhost:8000
```

---

## Test Questions

| # | Question | What it tests |
|---|----------|--------------|
| 1 | "Which production orders are at risk this week?" | All-orders risk scan |
| 2 | "Why is order 100045 at risk?" | MRP + capacity + risk analysis |
| 3 | "What should I do?" | Planner recommendation + guardrails |
| 4 | "What if PO 4500012345 arrives two days earlier?" | What-if simulation |
| 5 | "Release order 100045 now." | Read-only guardrail (agent declines) |

---

## Capacity Classification Thresholds

| Classification | Utilization | Badge |
|----------------|-------------|-------|
| NORMAL | < 90% | 🟢 |
| WATCH | 90–100% | 🟡 |
| HIGH | 100–110% | 🟠 |
| CRITICAL | > 110% | 🔴 |

> ⚠️ Prototype thresholds — not SAP standard

---

## Deployment to SAP BTP

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the full deployment guide including:
- SAP AI Core service setup
- GPT-4o model deployment
- Production OAuth2 token refresh (client credentials flow)
- Post-deployment validation steps
- Troubleshooting

---

*All data is SIMULATED. This is a prototype for demonstration purposes only.*
