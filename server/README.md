# Athena server

FastAPI backend for Athena: auth, projects, the multi-agent pipeline, consistency checks,
code search, export, and real-time progress over WebSockets.

## Setup

Requirements: Python 3.11+ (3.12 recommended), Docker Desktop (for PostgreSQL + pgvector).

```bash
cd server

# 1. Python environment (uv installs Python 3.12 for this folder only)
python -m pip install --user uv
python -m uv sync --python 3.12                   # add --extra embeddings for real semantic search (PyTorch)

# 2. Configuration
cp .env.example .env            # then fill in SECRET_KEY, ANTHROPIC_API_KEY, GitHub OAuth, ...

# 3. Database
docker compose up -d            # PostgreSQL 17 + pgvector on localhost:5433 (not 5432)
.venv/Scripts/python -m alembic upgrade head      # macOS/Linux: .venv/bin/python

# 4. Run
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs. The frontend dev server (`client/`, `npm run dev`) proxies `/api` here.

### Running with a free local model (Ollama)

1. Install Ollama from https://ollama.com and pull a model: `ollama pull qwen2.5-coder:7b`
   (about 4.7 GB; runs on a 16 GB laptop on CPU, slowly: a spec takes about a minute).
2. In `.env` set every `AGENT_*_PROVIDER=local` and `OLLAMA_MODEL=qwen2.5-coder:7b`.
3. Restart the backend. Answers are constrained to the agent's JSON schema by Ollama's `format` option.

### Running without API keys

Set every `AGENT_*_PROVIDER=fake` in `.env`. Agents then return built-in sample output, so the whole
pipeline works for demos and frontend development. Set `EMBEDDINGS_BACKEND=hash` to skip PyTorch too.

## Tests

```bash
.venv/Scripts/python -m pytest          # SQLite + fake providers: no keys, no network
# Integration tests use the Docker Postgres on 5433 (database athena_test) and are skipped if it is down.
.venv/Scripts/python -m ruff check app alembic
```

## Research (Paper 1): strict vs naive handoffs

`app/research/naive.py` is the baseline: the same agents and role instructions, but they hand plain
Markdown to each other (no schema, no validation, no retry). The code is read from `FILE: path` + fenced
blocks by a lenient parser. Both modes then go through the same static consistency checks.

```bash
# Pilot: first 3 ideas from research/ideas.yaml, both modes, results in research/results/pilot/
.venv/Scripts/python -m app.research.benchmark --limit 3 --out research/results/pilot
# Full run: all 10 ideas, 2 repeats each (overnight on a CPU-only laptop)
.venv/Scripts/python -m app.research.benchmark --repeats 2 --out research/results/full
# Rebuild summary.md from existing CSVs without calling any model
.venv/Scripts/python -m app.research.benchmark --out research/results/pilot --summary-only
```

Output: `pipelines.csv` (one row per idea x mode x repeat), `agent_runs.csv`, `checks.csv`,
`run-config.json` (models, settings, git commit) and `summary.md` (tables plus a methods paragraph).
Interrupted runs resume: finished pipelines are skipped. The Anthropic refusal fallback is forced off.

## How it works

```
app/
  api/        routes: auth, projects (files, chat), pipeline (stages, runs, checks, metrics), export, ws
  core/       config (pydantic-settings), db (async SQLAlchemy), security (bcrypt, JWT, cookies, Fernet)
  models/     SQLAlchemy tables, including agent_runs and consistency_checks (research measurements)
  schemas/    Pydantic v2: API bodies and strict agent input/output schemas (schemas/agents/)
  agents/     idea, stack, code, eva, summary, chat (LLM) and deploy (rule-based)
  llm/        provider layer: anthropic ("api"), ollama ("local"), fake; chosen per agent in .env
  checker/    static consistency checks between agent outputs
  services/   pipeline orchestration, progress hub, embeddings, GitHub, zip export
  templates/  Jinja2 deployment templates (Dockerfile, compose, Render, GitHub Actions)
  tests/      pytest suite
```

**Pipeline:** `POST /api/projects/{id}/stages/{stage}/run` with stage `idea`, `stack`, `code`, `eva`,
`export` or `deploy`. It returns 202 immediately; progress arrives on `ws://.../api/ws/projects/{id}` as
events: `stage_started`, `agent_started`, `agent_succeeded`, `checks_completed`, `stage_completed` /
`stage_failed`.

**Strict schemas (Research Paper 1):** every agent reads one Pydantic model and must return another
(`extra="forbid"`). Invalid output is retried with the validation error fed back, up to
`AGENT_MAX_RETRIES` times. Agents never exchange free text.

**Measurements:** every agent run is stored in `agent_runs` (provider, model, duration, input/output
tokens, retries, each validation error, pass/fail, full input and output JSON). Every consistency check
is stored in `consistency_checks` (name, pass/fail, severity, details, duration). `GET /api/metrics`
aggregates both per agent and per check. For analysis, query the tables directly, for example:

```sql
select agent, count(*), avg(duration_ms), avg(retries),
       avg(case when status = 'succeeded' and retries = 0 then 1.0 else 0 end) as first_try_rate
from agent_runs group by agent;
```

**Safety:** generated code is never executed on the server. The checker only parses: Python with `ast`
and pyflakes, JSON / YAML / TOML as data, JavaScript and TypeScript with a bracket-balance scan and import
extraction. GitHub tokens are stored encrypted (Fernet, key derived from `SECRET_KEY`).

**Auth:** bcrypt passwords; 15-minute access token and 7-day refresh token in httpOnly, SameSite=Lax
cookies; refresh tokens rotate on every use and a reused token revokes the whole session. GitHub OAuth
signs users in and stores the token used for "Push to GitHub".
