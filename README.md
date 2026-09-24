# Athena

A web platform where a student describes an app idea and AI agents take it through
**Idea & Spec → Tech Stack → Code → Export → Deploy**, then write a learning summary that explains
what was built. Final year project, supporting two research papers.

| Folder | What |
| --- | --- |
| [`client/`](client/) | React 19 + TypeScript + Vite frontend (Tailwind, shadcn/ui, Monaco, TanStack Query) |
| [`server/`](server/) | FastAPI backend: agents, consistency checker, PostgreSQL + pgvector, research tooling |

## Agents

| Agent | Does | Colour |
| --- | --- | --- |
| Idea Agent | Turns the idea into a structured spec (users, core features, scope) | pink |
| Tech Stack Agent | Picks a free, student-friendly stack with reasons and alternatives | sky |
| Code Agent | Generates the first version of the app into the built-in editor | mauve |
| EVA | Virtual users Alpha, Bravo and Charlie try the app on paper and report issues | peach |
| Deployment & Summary Agent | Rule-based deploy files (Dockerfile, compose, Render, GitHub Actions) plus a learning summary | green |

Every agent reads and writes a strict Pydantic schema. Invalid answers are retried with the exact
validation error. A static consistency checker (syntax, pyflakes, missing dependencies, stack match,
spec completeness) runs after each stage. Generated code is never executed.

## First-time setup

Needs: Git, Node 20+, Python 3.12, Docker Desktop, and optionally [Ollama](https://ollama.com) for a free local model.

```bash
git clone https://github.com/pxsha23/ProjectAthena.git
cd ProjectAthena/server
python -m pip install --user uv
python -m uv sync --python 3.12            # creates .venv with Python 3.12 and all dependencies
cp .env.example .env                  # then set SECRET_KEY (command is in the file)
docker compose up -d                  # Postgres + pgvector on port 5433
python -m uv run alembic upgrade head
python -m uv run uvicorn app.main:app --reload --port 8000

# second terminal
cd ProjectAthena/client
npm install
npm run dev                           # http://localhost:5173
```

Which AI model runs each agent is set in `server/.env`:

- `fake`: built-in sample answers, no key, instant. Good for UI work.
- `local`: Ollama on your machine, free. `ollama pull qwen2.5-coder:7b`, then set `OLLAMA_MODEL=qwen2.5-coder:7b`.
- `api`: the Anthropic API, needs `ANTHROPIC_API_KEY`.

Never commit `.env` and never paste keys into chats or issues. Each person makes their own `.env`.

## Checks before you push

```bash
cd server && python -m uv run pytest && python -m uv run ruff check .
cd client && npm run build
```

## Research

- **Paper 1** compares strict schema handoffs with a naive free-text mode on the same ideas and the
  same checks. Run it with `python -m uv run python -m app.research.benchmark` (see
  [server/README.md](server/README.md#research-paper-1-strict-vs-naive-handoffs)). Ideas live in
  [`server/research/ideas.yaml`](server/research/ideas.yaml); results go to `server/research/results/`.
- **Paper 2** covers the full platform and a user study. Every agent run and check is logged to the
  database, and `GET /api/metrics` summarises it.

## Deploy

Free public deployment: the frontend on Vercel, the backend and database on Render.

- `render.yaml`: Render Blueprint for the API and a free Postgres database (New, then Blueprint).
- `client/vercel.json`: forwards `/api` to the Render service. Set the Vercel project's Root Directory to `client`.
- The free Render instance cannot run a local model, so agents default to `fake` there. Use `api` with an
  Anthropic key for real answers.
