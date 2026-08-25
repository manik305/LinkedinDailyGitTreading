# 🚀 Autonomous Open-Source Spotlight Agent
### *GitHub Trending → EURI LLM (Human-First Post) → Telegram HITL → LinkedIn*

An autonomous, production-grade agent built with **FastAPI**, **LangGraph**, and the **EURI LLM API** that discovers trending open-source repositories ($>5\text{k}$ stars), ingests real documentation, synthesizes deeply authentic technical LinkedIn posts (written in a real practitioner voice, zero robotic AI fluff), routes them to Telegram for one-click Human-in-the-Loop review, and publishes to LinkedIn.

---

## 🌟 Key Features

- **🧠 Authentic Human Developer Voice**: Replaces generic AI buzzwords (*"delve"*, *"game changer"*, *"unleash"*) with authentic practitioner insights, architectural trade-offs, and clean formatting.
- **⚡ EURI LLM Integration**: Powered by Euron's OpenAI-compatible endpoint (`https://api.euron.one/api/v1/euri`) with support for models like `gpt-4.1-mini`, `gpt-4o`, `gpt-4o-mini`, and `claude-3-5-sonnet`.
- **🎯 Parameter Calibrated**: Configured with `max_tokens: 1500` (no truncated posts) and `temperature: 0.55` (creative natural phrasing strictly grounded in README facts).
- **📅 Strict 1-Post-Per-Day Cadence**: Guaranteed single daily post enforced at both scheduler and SQLite database query levels.
- **📱 Telegram Human-in-the-Loop (HITL)**: Instant mobile previews with interactive inline buttons: `[ ✅ Accept & Post ]`, `[ 🔄 Regenerate ]`, `[ ❌ Skip Repo ]`.
- **📈 LangSmith Real-Time Tracing**: Native LangGraph and OpenAI client wrapping (`langsmith.wrappers.wrap_openai` & `@traceable`) for live tracing of every LLM call, prompt, token usage, latency, tool call, and graph transition.
- **🌐 FastAPI Backend Server**: Full REST API and webhook receiver (`/health`, `/api/v1/run-daily-pipeline`, `/api/v1/telegram-webhook`, `/api/v1/history`).
- **💾 SQLite Persistence**: Version-controlled local database tracking posted repositories, timestamps, and LinkedIn post URNs.

---

## 🏗️ Architecture & Workflow

```text
[ Daily Trigger: 09:00 AM IST (03:30 AM UTC) / FastAPI REST ]
                    │
                    ▼
          [ Fetch Trending Repos ] (GitHub API > 5k stars)
                    │
                    ▼
          [ SQLite Daily & Dedup Guard ] ──(Already Posted Today?)──► [ End: Quota Met ]
                    │
                    ▼ (New Unposted Repo)
          [ Ingest & Sanitize README ]
                    │
                    ▼
          [ EURI LLM Synthesis ] (gpt-4.1-mini / gpt-4o | 1500 tokens | 0.55 temp)
          [ 🔍 LangSmith Live Traces: Prompts, Tokens, Latency & Spans ]
                    │
                    ▼
          [ Telegram HITL Dispatch ] ◄────────────────┐ (🔄 Regenerate)
                    │                                  │
                    ├──────────────────────────────────┘
                    ├──(❌ Skip)──► [ Next Repo Loop ]
                    │
                    ▼ (✅ Accept & Post)
          [ Publish to LinkedIn API ]
                    │
                    ▼
          [ Persist State to SQLite ]
```

---

## ⚙️ Quickstart & Setup

### 1. Clone & Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your credentials:
```powershell
cp .env.example .env
```

```env
# EURI LLM API Configuration
EURI_API_KEY=your_euri_key_here
EURI_BASE_URL=https://api.euron.one/api/v1/euri
EURI_MODEL=gpt-4.1-mini
EURI_MAX_TOKENS=1500
EURI_TEMPERATURE=0.55

# LangSmith Real-Time Observability & Tracing
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...your_langsmith_api_key_here...
LANGSMITH_PROJECT=github-linkedin-spotlight
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

# Optional: GitHub Personal Access Token for higher rate limits
GITHUB_TOKEN=

# Telegram HITL (BotFather)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=your_chat_id

# LinkedIn REST API
LINKEDIN_ACCESS_TOKEN=your_oauth_token
LINKEDIN_PERSON_URN=urn:li:person:abcdef123
```

---

## 🐳 Docker & Docker Compose Setup

Run the entire application in isolated, reproducible Docker containers with automated healthchecks and persistent storage.

### 1. Build and Start the FastAPI Web Service
Starts the API service on `http://localhost:8000` with the SQLite database stored on the host (`./data`):
```bash
docker compose up -d --build
```

- **Healthcheck & Status**:
  ```bash
  docker compose ps
  curl http://localhost:8000/health
  ```
- **Stream Logs**:
  ```bash
  docker compose logs -f spotlight-api
  ```
- **Stop Service**:
  ```bash
  docker compose down
  ```

### 2. Execute a Single Daily Spotlight Run (CLI / Dispatch)
To run a one-shot execution (fetching trending repos, generating draft via EURI, dispatching Telegram HITL, updating SQLite database):
```bash
docker compose run --rm spotlight-cli
```

---

## 🚀 Running the Application (Locally / Without Docker)

### Mode A: FastAPI Server Mode (Recommended for Webhooks & Live Services)
```powershell
python main.py
# or
uvicorn src.api:app --reload --port 8000
```
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: `GET http://localhost:8000/health`
- **Trigger Pipeline**: `POST http://localhost:8000/api/v1/run-daily-pipeline`
- **View History**: `GET http://localhost:8000/api/v1/history`

### Mode B: CLI / Scheduled Cron Mode (GitHub Actions)
```powershell
python main.py run
```
Executes discovery, LLM post generation, Telegram dispatch, and state persistence directly in the console.

---

## 📊 LLM Model Recommendations

| Model | Recommended Use Case |
| :--- | :--- |
| **`gpt-4.1-mini`** *(Configured Default)* | Ultra-fast token generation, high instruction adherence, cost-effective. |
| **`gpt-4o`** | Deepest reasoning, exceptional human nuance, best for complex system architecture breakdowns. |
| **`claude-3-5-sonnet`** | Industry-leading prose; natural developer tone. |
| **`deepseek-chat`** | High code reasoning and ultra-low cost. |

---

## 🔒 Strict 1-Post-Per-Day Rule

The agent prevents duplicate or frequent posting by querying SQLite:
```sql
SELECT COUNT(*) FROM posted_repos 
WHERE date(posted_at) = date('now') AND status = 'POSTED';
```
If a post was already published today, further pipeline runs are gracefully skipped with status `DAILY_QUOTA_REACHED`.
