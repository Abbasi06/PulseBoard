# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# PulseFeed

## What this is
A local-first, AI-powered knowledge feed. Users enter their occupation, field, and interests. The app fetches the latest news and upcoming events, scores them with a local LLM (llama.cpp), generates personalised 2-sentence summaries, and shows everything in a clean dashboard. No API key required — the model is auto-downloaded on first run.

## Tech stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy, SQLite, JWT auth (httpOnly cookies)
- Frontend: React 19, Vite, TailwindCSS v4, React Router v7, Framer Motion
- AI: llama-cpp-python (local GGUF model, auto-selected by RAM) + DuckDuckGo search (`duckduckgo-search`)
- Package manager: `uv` for Python, `npm` for Node

## Environment setup
No API keys required. To start:
```
python bootstrap.py        # recommended — installs deps, builds frontend, opens browser
# or manually:
cd pulsefeed/backend && uv sync --group dev
cd pulsefeed/frontend && npm install
```
Set `PULSEFEED_NO_LLM=1` to skip model download (useful for tests and CI).

## Commands

### Run
```
python bootstrap.py                                              # full auto-start
cd pulsefeed/backend && uv run --no-sync uvicorn main:app --reload --port 8000
cd pulsefeed/frontend && npm run dev
```

### Lint & type-check (run before every commit)
```
cd pulsefeed/backend && uv run --no-sync ruff check . && uv run --no-sync mypy .
cd pulsefeed/frontend && npm run lint
cd pulsefeed/frontend && npx prettier --write src/
```

### Test
```
cd pulsefeed/backend && PULSEFEED_NO_LLM=1 uv run --no-sync pytest tests/ -v
cd pulsefeed/frontend && npm run test       # run once
cd pulsefeed/frontend && npm run test:watch # watch mode
```

## Architecture

### Data flow
1. User submits profile (name, occupation, field, chips) via `POST /users` → JWT cookie set
2. `GET /feed/{user_id}` and `GET /events/{user_id}` check cache: if `fetched_at` is older than the user's configured TTL (3/6/12 h), background generation is triggered; stale items are returned immediately with `X-Feed-Generating: true` header
3. `agents/feed_personalizer.py` calls `content/pipeline.py` via `asyncio.to_thread`:
   - `content/fetcher.py` builds DuckDuckGo queries from profile and fetches results (no LLM)
   - `llm/engine.py` scores each result 1–10 for relevance (LLM); items scoring < 6 are dropped
   - `llm/engine.py` generates personalised 2-sentence summaries for top 15 (LLM)
   - Results capped at 20 news / 10 events and stored in SQLite
4. Model load state streamed to frontend via `GET /system/model-progress` (SSE)
5. Frontend fetches `GET /feed/{user_id}` and `GET /events/{user_id}`; force refresh via `POST /feed/{user_id}/refresh`

### Backend modules (`pulsefeed/backend/`)
- `main.py` — FastAPI app, CORS config (localhost:3000 + :5173–:5182 in dev), security middleware, lifespan startup (table creation + raw SQL column migrations + LLM background load); serves built React SPA as static files in production
- `database.py` — SQLAlchemy engine + session factory; DB lives at `~/.pulsefeed/pulseboard.db`; override with `DATABASE_URL` env var; in-memory SQLite for tests
- `models.py` — ORM models: `User`, `FeedItem`, `Event`, `FeedBrief` (User has cascade-delete relationships to all three)
- `schemas.py` — Pydantic models; `UserCreate`/`UserUpdate` validators handle whitespace stripping, tag deduplication, enum checks
- `auth.py` — JWT creation/validation; tokens stored as httpOnly cookies (30-day expiry, `secure=False` in dev); `SECRET_KEY` defaults to `"dev-secret-change-before-production"`
- `routes/users.py` — CRUD for user profiles + login/logout; `POST /users` creates user and sets cookie; `GET /users/me` validates cookie
- `routes/feed.py` — returns cached feed items; auto-triggers background generation if stale; `PATCH /feed/items/{id}/{like,dislike,save,click}` updates engagement flags; 60-second refresh cooldown
- `routes/events.py` — same pattern as feed; `PATCH /events/items/{id}/like`
- `routes/system.py` — `GET /system/status` (model state); `GET /system/model-progress` (SSE stream, polled by frontend setup screen)
- `agents/feed_personalizer.py` — thin async wrappers: `personalize_feed()` and `personalize_events()` run the pipeline in a thread via `asyncio.to_thread`
- `content/pipeline.py` — synchronous LLM pipeline: fetch → relevance filter (threshold 6/10) → summarise → return list[dict]
- `content/fetcher.py` — builds 3–5 DDG queries from user profile; deduplicates results; 0.8 s sleep between queries
- `llm/engine.py` — singleton `LLMEngine`; thread-safe via `threading.Lock`; `.chat()`, `.score_relevance()`, `.summarize()`, `.generate_brief()`
- `llm/model_manager.py` — detects RAM/GPU, selects tier (tiny/small/medium), downloads GGUF from HuggingFace with progress tracking into `state{}` dict
- `logging_config.py` — JSON structured logging via `configure_json_logging()`
- `security/` — `AuditMiddleware`, `SecurityHeadersMiddleware`, `feed_rate_limit`, `refresh_rate_limit`, `sanitize_llm_input`

### Frontend structure (`pulsefeed/frontend/src/`)
- `context/AuthContext.jsx` — on mount calls `GET /users/me` to validate httpOnly cookie; provides `user`, `isAuthenticated`, `login()`, `logout()`; all fetches use `credentials: 'include'`
- `pages/LandingPage.jsx` — public landing page (**owned by a separate developer — do not modify**)
- `pages/Onboarding.jsx` — profile creation form with chip selection and field taxonomy
- `pages/Dashboard.jsx` — two tabs (Feed, Saved); inline `EventCard`; `FeedBrief` panel; like/dislike/save/click engagement; refresh triggers feed + events in parallel
- `pages/Settings.jsx` — pre-populated edit form with chip and taxonomy selectors; success banner on save
- `components/DashboardLayout.jsx` — mobile top bar + floating desktop brand pill with popup; wraps protected routes via `<Outlet />`
- `components/TagInput.jsx` — reusable tag input
- `components/NewsCard.jsx` — topic colour badges; image fallback to `picsum.photos` seeded by title hash
- `components/EventCard.jsx` — standalone component (used by tests); Dashboard renders its own local variant
- `components/BrainLoader.jsx` — animated loader shown during feed generation
- `components/SkeletonCard.jsx` — pulse placeholder during initial load
- `components/WarpBackground.jsx` — particle network shown on onboarding
- `components/landing/` and `components/hero/` — **landing page components, owned by a separate developer — do not modify**
- `lib/validation.js` — shared frontend validation helpers
- `config.js` — exports `API_URL`; defaults to `http://localhost:8000`; override via `VITE_API_URL` env var

### Key config
`pulsefeed/frontend/src/config.js` exports `API_URL`. In production, backend serves the built SPA at the same origin (port 8000), so the URL is the same. In dev, the Vite dev server runs on port 3000/5173 and fetches `:8000`.

## Validation rules

### Backend (Pydantic — `schemas.py`)
- `name`: required, non-empty, max 100 chars
- `occupation`: required, non-empty, max 150 chars
- `selected_chips`: required, 1–5 items, each max 50 chars, no duplicates
- `field`: optional, max 100 chars
- `sub_fields`: optional, max 10 items, each max 100 chars, no duplicates
- `taxonomy_tags`: optional; values must be from `VALID_TAXONOMY_TAGS` frozenset
- `excluded_topics`: optional, max 20 items, each max 50 chars
- `exploration_mode`: `"narrow"` or `"broad"` (default `"broad"`)
- `refresh_interval_hours`: must be 3, 6, or 12 (default 6)
- Strip and `sanitize_llm_input` all string fields before saving
- Return HTTP 422 with a clear message for any failure

### Frontend
- Show inline errors for empty name, occupation, or zero chips on submit
- Tags: trim whitespace, silently skip empty/duplicate (case-insensitive)/over-limit tags
- Disable submit while API call is in progress
- Show a friendly error banner on API failure — never expose raw error objects

### Pipeline validation (`content/pipeline.py`)
- Items are scored 1–10 for relevance; items scoring < 6 are dropped before summarisation
- `title` defaults to `"Untitled"`, `summary` to snippet[:300], `source` extracted from URL domain
- Discard events where `name` or `date` is missing/Unknown
- Cap at 20 feed items / 10 events per refresh
- Pipeline returns empty list if LLM is not ready; routes return stale cached data in that case

### Tests
- `pulsefeed/backend/tests/conftest.py` — `db` fixture (in-memory SQLite with `StaticPool`) + `client` fixture (`TestClient` with `get_db` overridden); `StaticPool` required so all connections share the same in-memory DB
- Set `PULSEFEED_NO_LLM=1` in test environment to skip model loading
- **404 vs 403 note:** feed/events/user-update routes check `user_id != current_user_id` (→ 403) *before* the DB lookup (→ 404); tests that assert 404 must forge a JWT for the non-existent `user_id` via `create_access_token(99999)`
- Frontend tests: `vitest` + `@testing-library/react` in `src/components/__tests__/`; `<img alt="">` has ARIA role `"presentation"` — use `screen.getByRole('presentation')` for image assertions

## Claude Code configuration (`.claude/`)

### Agents
Specialized subagents available via the Agent tool:
- `frontend-developer` — React/Vite/TailwindCSS component work
- `ui-ux-designer` — UI/UX design decisions and layout
- `backend-architect` — FastAPI, SQLAlchemy, API design
- `code-reviewer` — code quality and review
- `debugger` — root-cause analysis and bug fixing
- `context-manager` — managing large context and summarisation
- `mcp-expert` — MCP server configuration

### Skills
Invocable via the Skill tool (`/skill-name`):
- `ui-ux-pro-max` — advanced UI/UX with design data (colors, typography, icons, React patterns)
- `ui-design-system` — design token generation (`scripts/design_token_generator.py`)
- `frontend-design` — frontend design guidance
- `senior-backend` — backend best practices; includes API load tester, scaffolder, and DB migration tool scripts

### Hooks (`.claude/settings.json`)
All hooks run on `PostToolUse`:
- **simple-notifications** (`*`) — desktop notification on every tool completion (macOS/Linux)
- **smart-commit** (`Edit`) — auto-stages and commits edited files with size-classified message
- **smart-commit** (`Write`) — auto-commits newly written files with `Add new file: …`
- **security-scanner** (`Edit|Write`) — runs semgrep, bandit (`.py` only), gitleaks, and a regex secrets check after every file change

### Permissions (`.claude/settings.json`)
- **Allow:** `npm run lint`, `npm run test:*`, `npm run build`, `npm start`
- **Deny:** read or write to any `.env` / `.env.*` file

### Status line
`python3 .claude/scripts/context-monitor.py` — displays context usage bar, percentage, token count, session duration, and cost; turns red with `⚠ COMPACT SOON` at 85% context usage.

## Code conventions
- Python: snake_case, type hints on **all** parameters and return types, no function > 40 lines, no bare `except`
- React: functional components only, camelCase, no `console.log` in committed code
- All Python commands run via `uv run --no-sync` (venv already set up via `uv sync --group dev`) — never activate the venv manually
- Tests: in-memory SQLite for backend tests; set `PULSEFEED_NO_LLM=1` — no real LLM calls in tests

## Pre-commit checklist
Fix all failures before marking any feature complete:
```
cd pulsefeed/backend && uv run --no-sync ruff check . && uv run --no-sync mypy . && PULSEFEED_NO_LLM=1 uv run --no-sync pytest tests/ -v
cd pulsefeed/frontend && npm run lint && npx prettier --write src/ && npm run test
```
