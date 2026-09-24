# Athena: frontend

Type an app idea; AI agents take it from **Idea & Spec → Tech Stack → Code → Export → Deploy**.
This is the React frontend. It talks to the FastAPI backend in `../server` through the Vite proxy (`/api` and the WebSocket go to http://localhost:8000), so start the backend first.

## Run

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production build
```

Sign up with an email and password, or with GitHub if GitHub OAuth is set up in `server/.env`.

## Where things live

| Path | What |
| --- | --- |
| `src/styles/globals.css` | Theme palettes (Black default, Mocha) as CSS variables, wired into Tailwind: use `bg-panel`, `text-muted`, `text-lavender`... The Monaco theme reads the same variables. |
| `src/lib/theme.tsx` | Theme provider and switcher state (saved in localStorage). |
| `src/lib/api/` | `client.ts` (fetch wrapper with cookie refresh), `endpoints.ts` (every backend route), `queries.ts` (TanStack Query hooks). |
| `src/lib/types.ts` | TypeScript types matching the backend Pydantic schemas. |
| `src/lib/agents.ts` | Agents, pipeline stages, and the static agent → colour class maps. |
| `src/lib/auth.tsx` | Auth context: current user, sign in / sign up / sign out against the backend. |
| `src/features/landing/` | Landing page sections and animations. |
| `src/features/workspace/` | Project workspace: stepper, explorer, Monaco editor, agent chat, EVA, checks, output, code search. `use-project-events.ts` listens to live progress over the WebSocket. |
| `src/components/ui/` | shadcn/ui-style primitives (Radix + cva) themed with the tokens. |

## Notes

- Monaco is bundled locally (no CDN) and only loaded on the workspace route.
- On screens under 1024px the workspace switches from resizable panels to a tabbed layout.
- "Download .zip" and "Push to GitHub" are served by the backend (`/api/projects/{id}/export/...`).
