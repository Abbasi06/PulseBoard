"""
PulseFeed — Main Application
-----------------------------
Local-first AI news feed powered by llama.cpp.
Runs on port 8000; serves both the API and the built React SPA.

Start via bootstrap.py (recommended) or:
    cd pulsefeed/backend && uv run uvicorn main:app --port 8000
"""
from __future__ import annotations

import logging
import os
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import sqlalchemy
import sqlalchemy.exc
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from logging_config import configure_json_logging

configure_json_logging()
logger = logging.getLogger(__name__)

# Load .env — service dir first, repo root as fallback
load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path(__file__).parents[2] / ".env")

from database import Base, engine  # noqa: E402
from routes import events, feed, users  # noqa: E402
from routes.system import router as system_router  # noqa: E402
from security import AuditMiddleware, SecurityHeadersMiddleware  # noqa: E402


def _run_migrations() -> None:
    migrations = [
        "ALTER TABLE feed_items ADD COLUMN image_url TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE feed_items ADD COLUMN published_date TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE feed_items ADD COLUMN liked BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE feed_items ADD COLUMN disliked BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE feed_items ADD COLUMN saved BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE feed_items ADD COLUMN read_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE events ADD COLUMN image_url TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE events ADD COLUMN liked BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN preferred_formats TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE users ADD COLUMN field TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE users ADD COLUMN sub_fields TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE users ADD COLUMN refresh_interval_hours INTEGER NOT NULL DEFAULT 6",
        "ALTER TABLE users ADD COLUMN taxonomy_tags TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE users ADD COLUMN excluded_topics TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE users ADD COLUMN exploration_mode VARCHAR(20) NOT NULL DEFAULT 'broad'",
        (
            "CREATE TABLE IF NOT EXISTS feed_briefs ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE, "
            "headline TEXT NOT NULL DEFAULT '', "
            "signals TEXT NOT NULL DEFAULT '[]', "
            "top_reads TEXT NOT NULL DEFAULT '[]', "
            "watch TEXT NOT NULL DEFAULT '[]', "
            "generated_at TEXT NOT NULL DEFAULT (datetime('now')))"
        ),
        "CREATE INDEX IF NOT EXISTS idx_feed_items_user_fetched ON feed_items(user_id, fetched_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_events_user_fetched ON events(user_id, fetched_at DESC)",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(sqlalchemy.text(sql))
                conn.commit()
            except sqlalchemy.exc.OperationalError as exc:
                conn.rollback()
                if "already has a column named" not in str(exc) and "already exists" not in str(exc):
                    logger.warning("Migration skipped: %s", exc)


def _start_llm_in_background() -> None:
    """Prepare + load the model in a daemon thread so startup is instant."""
    def _worker() -> None:
        try:
            from llm.model_manager import prepare_model, state
            from llm.engine import LLMEngine

            state["status"] = "checking"
            config = prepare_model()

            if state.get("status") == "disabled":
                LLMEngine.get().load(model_path="", gpu_type="cpu", n_ctx=2048)
                return

            state["status"] = "loading"
            LLMEngine.get().load(
                model_path=config["model_path"],
                gpu_type=config["gpu_type"],
                n_ctx=config["n_ctx"],
            )
            state["status"] = "ready"
        except Exception as exc:
            logger.error("LLM startup failed: %s", exc)
            from llm.model_manager import state
            state["status"] = "error"
            state["error"] = str(exc)

    t = threading.Thread(target=_worker, daemon=True, name="llm-loader")
    t.start()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _start_llm_in_background()
    yield


app = FastAPI(title="PulseFeed", lifespan=lifespan)

# CORS — localhost only in dev; set ALLOWED_ORIGIN env var in any server deploy
_prod_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGIN", "").split(",") if o.strip()]
_ALLOWED_ORIGINS = _prod_origins if _prod_origins else [
    "http://localhost:3000",
    *[f"http://localhost:{p}" for p in range(5173, 5183)],
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Feed-Generating", "X-Events-Generating", "Retry-After"],
)
app.add_middleware(AuditMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(users.router)
app.include_router(feed.router)
app.include_router(events.router)
app.include_router(system_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pulsefeed"}


# Serve built React SPA — must be last so API routes take priority
_static_dir = Path(__file__).parents[1] / "frontend" / "dist"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="spa")
else:
    logger.info("Frontend dist/ not found — run `npm run build` in pulsefeed/frontend")
