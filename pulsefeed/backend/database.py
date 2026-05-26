"""
SQLite database configuration for PulseFeed.

Database file lives at ~/.pulsefeed/pulseboard.db so it persists across
app updates and reinstalls. Override with DATABASE_URL env var if needed.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_default_path = Path.home() / ".pulsefeed" / "pulseboard.db"
_default_path.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", f"sqlite:///{_default_path}"
)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
