# Deployment Guide — Production Planning Risk Agent

> **data_source: SIMULATED (prototype)** — No real SAP system is connected.
> Version: 1.0.0

---

## Pre-Deployment Prerequisite Checklist

Run this checklist before every deployment attempt.

### ✅ Artifacts — All Present

| Artifact | Path | Status |
|----------|------|--------|
| Deployment manifest | `solution.yaml` | ✅ |
| Agent entry point | `agent/main.py` | ✅ |
| FastAPI server | `agent/server.py` | ✅ |
| GPT-4o agent + tool-calling | `agent/agent.py` | ✅ |
| Four planning skills | `agent/skills.py` | ✅ |
| Simulated data layer | `agent/data.py` | ✅ |
| Python dependencies | `agent/requirements.txt` | ✅ |
| CF process declaration | `agent/Procfile` | ✅ |
| Python runtime pin | `agent/runtime.txt` | ✅ |
| React UI static build | `agent/static/index.html` | ✅ |
| React JS bundle | `agent/static/assets/*.js` | ✅ |
| React CSS bundle | `agent/static/assets/*.css` | ✅ |

### ❌ Blockers — Must Resolve Before Deploying

| # | Blocker | Severity | Section |
|---|---------|----------|---------|
| 1 | SAP AI Core service instance and credentials | 🔴 BLOCKING | [§1](#1-sap-ai-core-service-instance) |
| 2 | GPT-4o model deployment in AI Core | 🔴 BLOCKING | [§2](#2-gpt-4o-model-deployment) |
| 3 | `AICORE_BASE_URL` and `AICORE_API_KEY` env vars | 🔴 BLOCKING | [§3](#3-environment-variables) |

---

## 1. SAP AI Core Service Instance

### What you need

An SAP AI Core service instance with the **`extended`** service plan (required for LLM access via Generative AI Hub).

### How to create it

1. Open **SAP BTP Cockpit** → your subaccount → **Service Marketplace**
2. Search for **"SAP AI Core"**
3. Click **Create** → choose plan **`extended`**
4. Name it (e.g. `ai-core-pp-agent`) and confirm

> ℹ️ The `extended` plan is required. The `standard` plan does not include Generative AI Hub / LLM access.

### How to get the service key

1. Go to **Instances and Subscriptions** → find your AI Core instance
2. Click **Create Service Key** → name it (e.g. `pp-agent-key`)
3. Download or copy the JSON. It contains:

```json
{
  "clientid":     "<oauth-client-id>",
  "clientsecret": "<oauth-client-secret>",
  "url":          "https://<subdomain>.authentication.<region>.hana.ondemand.com",
  "serviceurls": {
    "AI_API_URL": "https://api.ai.<region>.aws.ml.hana.ondemand.com"
  }
}
```

You will use these values in [§3 — Environment Variables](#3-environment-variables).

---

## 2. GPT-4o Model Deployment

### Check if it already exists

1. Open **SAP AI Launchpad**
2. Go to **ML Operations** → **Deployments**
3. Look for a deployment with model **`gpt-4o`** and status **Running**

### Create it if missing

1. In AI Launchpad → **Generative AI Hub** → **Models**
2. Find **`gpt-4o`** (or `gpt-4o-mini` as a lower-cost alternative)
3. Click **Deploy** → confirm resource group and configuration
4. Wait for status **Running** (typically 2–5 minutes)

### Verify the model name

The model name used in `agent/agent.py` is controlled by the `PP_AGENT_MODEL` environment variable (default: `gpt-4o`). Confirm the exact model identifier shown in AI Launchpad matches this value. Common values:

| AI Launchpad model name | Use as `PP_AGENT_MODEL` |
|------------------------|------------------------|
| `gpt-4o` | `gpt-4o` |
| `gpt-4o-2024-05-13` | `gpt-4o-2024-05-13` |
| `gpt-4o-mini` | `gpt-4o-mini` |

---

## 3. Environment Variables

The agent requires two environment variables at runtime. **Never commit real credentials to source control.**

| Variable | Required | Description |
|----------|----------|-------------|
| `AICORE_BASE_URL` | Yes | AI Core API base URL (see below) |
| `AICORE_API_KEY` | Yes | Bearer token or OAuth2 access token |
| `PP_AGENT_MODEL` | No | LLM model name (default: `gpt-4o`) |
| `PORT` | No | Server port (default: `8000`; CF sets `8080`) |

### Constructing `AICORE_BASE_URL`

From your service key's `AI_API_URL`, append the AI Core API version path:

```
AICORE_BASE_URL = https://api.ai.<region>.aws.ml.hana.ondemand.com/v2
```

Example: `https://api.ai.eu10.aws.ml.hana.ondemand.com/v2`

---

## 4. Production Credential Approach — OAuth2 Client Credentials with Automatic Token Refresh

> ⚠️ A static bearer token expires (typically after 12 hours). For production use, implement automatic token refresh using the **OAuth2 Client Credentials** flow. The instructions below describe how to do this.

### Why not a static token

SAP AI Core uses OAuth2. A manually copied bearer token:
- Expires after ~12 hours
- Breaks the agent silently (returns 401 errors)
- Requires manual rotation

### Production approach: token refresh wrapper

Add a token-refresh wrapper to `agent/agent.py`. It fetches a new token before each LLM call if the current one has expired.

#### Step 1 — Add `requests` to requirements

```
# agent/requirements.txt  — add this line:
requests>=2.31.0
```

#### Step 2 — Replace the client initialisation in `agent/agent.py`

Replace the static client block:

```python
# REPLACE THIS (static, expires):
AICORE_BASE_URL = os.environ.get("AICORE_BASE_URL", "")
AICORE_API_KEY  = os.environ.get("AICORE_API_KEY", "")
client = OpenAI(base_url=AICORE_BASE_URL, api_key=AICORE_API_KEY)
```

With this token-refresh implementation:

```python
import time
import requests as _requests
from openai import OpenAI

# ---------------------------------------------------------------------------
# SAP AI Core OAuth2 token manager
# ---------------------------------------------------------------------------

AICORE_BASE_URL     = os.environ.get("AICORE_BASE_URL", "")
AICORE_CLIENT_ID    = os.environ.get("AICORE_CLIENT_ID", "")
AICORE_CLIENT_SECRET= os.environ.get("AICORE_CLIENT_SECRET", "")
AICORE_TOKEN_URL    = os.environ.get("AICORE_TOKEN_URL", "")   # ends with /oauth/token

# Fallback: allow a static key for local dev / testing
AICORE_API_KEY_STATIC = os.environ.get("AICORE_API_KEY", "")

_token_cache: dict = {"access_token": "", "expires_at": 0.0}

def _get_access_token() -> str:
    """Return a valid OAuth2 bearer token, refreshing automatically when expired."""
    # If static key provided (local dev), use it directly
    if AICORE_API_KEY_STATIC:
        return AICORE_API_KEY_STATIC

    # Refresh if missing or expiring within 60 seconds
    if time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    if not all([AICORE_CLIENT_ID, AICORE_CLIENT_SECRET, AICORE_TOKEN_URL]):
        raise EnvironmentError(
            "Missing AI Core OAuth2 credentials. Set AICORE_CLIENT_ID, "
            "AICORE_CLIENT_SECRET, and AICORE_TOKEN_URL (or AICORE_API_KEY for local dev)."
        )

    resp = _requests.post(
        AICORE_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(AICORE_CLIENT_ID, AICORE_CLIENT_SECRET),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"]   = time.time() + data.get("expires_in", 3600)
    return _token_cache["access_token"]


def _make_client() -> OpenAI:
    """Create an OpenAI client with the current valid token."""
    return OpenAI(
        base_url=AICORE_BASE_URL,
        api_key=_get_access_token(),
    )
```

Then replace the single `client.chat.completions.create(...)` call in the agentic loop with:

```python
# In ProductionPlanningAgent.chat(), replace:
response = client.chat.completions.create(...)

# With:
response = _make_client().chat.completions.create(...)
```

This recreates the client with a fresh token on every LLM call, refreshing from the token endpoint only when the cached token is about to expire.

#### Step 3 — Set the new environment variables

| Variable | Where to get it | Example |
|----------|----------------|---------|
| `AICORE_BASE_URL` | Service key → `serviceurls.AI_API_URL` + `/v2` | `https://api.ai.eu10.aws.ml.hana.ondemand.com/v2` |
| `AICORE_CLIENT_ID` | Service key → `clientid` | `sb-xxxxxxxx-...` |
| `AICORE_CLIENT_SECRET` | Service key → `clientsecret` | `xxxxxxxx-...` |
| `AICORE_TOKEN_URL` | Service key → `url` + `/oauth/token` | `https://<subdomain>.authentication.eu10.hana.ondemand.com/oauth/token` |

> `AICORE_API_KEY` is still supported as a fallback for local development (see [§5 — Local Testing](#5-local-testing-without-ai-core)).

---

## 5. Local Testing Without AI Core

**Yes — you can test the full agent with GPT-4o locally without SAP AI Core**, using your own OpenAI API key. The agent uses the OpenAI Python SDK, which is compatible with both SAP AI Core and the standard OpenAI API.

See [`README.md`](README.md) → **"Running Locally with Your Own OpenAI API Key"** for step-by-step instructions.

---

## 6. Deployment Steps (Once All Blockers Resolved)

### Option A — SAP Build (recommended)

1. Open this solution in SAP Build
2. Click **Deploy**
3. When prompted for environment variables, enter:
   - `AICORE_BASE_URL`
   - `AICORE_CLIENT_ID` (production) or `AICORE_API_KEY` (testing)
   - `AICORE_CLIENT_SECRET` (production)
   - `AICORE_TOKEN_URL` (production)
   - `PP_AGENT_MODEL` = `gpt-4o`
4. Confirm and complete deployment

### Option B — Manual CF push

```bash
# From the project root:

# 1. Build the React UI
npm --prefix ui run build

# 2. Log in to CF
cf login -a https://api.cf.<region>.hana.ondemand.com

# 3. Set credentials (do NOT put them in manifest.yml)
cf set-env pp-risk-agent AICORE_BASE_URL     "https://api.ai.<region>.aws.ml.hana.ondemand.com/v2"
cf set-env pp-risk-agent AICORE_CLIENT_ID    "<clientid>"
cf set-env pp-risk-agent AICORE_CLIENT_SECRET "<clientsecret>"
cf set-env pp-risk-agent AICORE_TOKEN_URL    "https://<subdomain>.authentication.<region>.hana.ondemand.com/oauth/token"
cf set-env pp-risk-agent PP_AGENT_MODEL      "gpt-4o"
cf set-env pp-risk-agent PORT                "8080"

# 4. Push
cf push pp-risk-agent \
  -p agent \
  -b python_buildpack \
  -m 512M \
  --no-start

# 5. Start
cf start pp-risk-agent
```

---

## 7. Post-Deployment Validation

After deployment, run these checks in order:

### 7.1 Health endpoint

```bash
# Replace <APP_URL> with your deployed URL
curl https://<APP_URL>/health
```

Expected response:
```json
{"status": "ok", "data_source": "SIMULATED", "scenario_date": "2025-01-13"}
```

### 7.2 Scenario data endpoint

```bash
curl https://<APP_URL>/scenario | python3 -m json.tool | head -20
```

Expected: JSON with `"data_source": "SIMULATED"` and 6 production orders.

### 7.3 Test question via API

```bash
curl -X POST https://<APP_URL>/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Which production orders are at risk this week?", "session_id": "deploy-test"}'
```

Expected: JSON `reply` field containing a risk table with orders 100045 and 100046 rated 🔴 HIGH.

### 7.4 Browser UI

Open `https://<APP_URL>/` in Chrome, Edge, or Firefox.

Expected: Chat interface with SIMULATED DATA banner, 5 test question buttons, guardrails panel.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `POST /chat` returns 500 | AI Core credentials missing or wrong | Check `AICORE_BASE_URL`, `AICORE_CLIENT_ID`, `AICORE_CLIENT_SECRET`, `AICORE_TOKEN_URL` env vars |
| `401 Unauthorized` from LLM | Token expired and auto-refresh not configured | Implement token refresh wrapper (§4) or renew static token |
| `404` on model | Wrong `PP_AGENT_MODEL` value | Check exact model name in AI Launchpad → Deployments |
| `GET /` returns 404 | React build missing | Run `npm --prefix ui run build` before deploying |
| Agent responds but no tool calls | System prompt not reaching LLM | Check token is valid; verify `gpt-4o` supports function-calling |
| App crashes on start | Missing Python dependency | Ensure `requirements.txt` is complete; check CF buildpack logs |

---

## 9. Security Notes

- **Never commit** `AICORE_API_KEY`, `AICORE_CLIENT_SECRET`, or any bearer token to source control
- The `.env` file is listed in `.gitignore` — only `.env.example` (with placeholder values) is committed
- CORS is currently set to `allow_origins=["*"]` — restrict to your domain in production:
  ```python
  # agent/server.py — production:
  allow_origins=["https://your-deployed-domain.hana.ondemand.com"]
  ```
- Session history is in-memory only — lost on restart, not persisted, not shared between users

---

*All data is SIMULATED. This agent is a prototype for demonstration purposes only.*
