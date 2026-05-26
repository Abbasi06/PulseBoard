from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    occupation: Mapped[str] = mapped_column(String(150), nullable=False)
    field: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    selected_chips: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sub_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    preferred_formats: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    refresh_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    taxonomy_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    excluded_topics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    exploration_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="broad")

    feed_items: Mapped[list[FeedItem]] = relationship(
        "FeedItem", back_populates="user", cascade="all, delete-orphan"
    )
    events: Mapped[list[Event]] = relationship(
        "Event", back_populates="user", cascade="all, delete-orphan"
    )
    brief: Mapped[Optional[FeedBrief]] = relationship(
        "FeedBrief", back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class FeedItem(Base):
    __tablename__ = "feed_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False, default="Untitled")
    summary: Mapped[str] = mapped_column(String, nullable=False, default="")
    source: Mapped[str] = mapped_column(String, nullable=False, default="Unknown")
    url: Mapped[str] = mapped_column(String, nullable=False, default="#")
    topic: Mapped[str] = mapped_column(String, nullable=False, default="General")
    image_url: Mapped[str] = mapped_column(String, nullable=False, default="")
    published_date: Mapped[str] = mapped_column(String, nullable=False, default="")
    liked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disliked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    saved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User", back_populates="feed_items")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False, default="")
    type: Mapped[str] = mapped_column(String, nullable=False, default="")
    url: Mapped[str] = mapped_column(String, nullable=False, default="#")
    reason: Mapped[str] = mapped_column(String, nullable=False, default="")
    image_url: Mapped[str] = mapped_column(String, nullable=False, default="")
    liked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship("User", back_populates="events")


class FeedBrief(Base):
    __tablename__ = "feed_briefs"
    __table_args__ = (UniqueConstraint("user_id", name="uq_feed_briefs_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    headline: Mapped[str] = mapped_column(String, nullable=False, default="")
    signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    top_reads: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    watch: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship("User", back_populates="brief")
