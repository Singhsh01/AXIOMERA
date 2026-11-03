from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        s = get_settings()
        _engine = create_engine(s.database_url, pool_pre_ping=True, pool_size=s.db_pool_size, max_overflow=s.db_max_overflow, pool_recycle=1800)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def reset_engine(url: str | None = None):
    """Used by tests to point the app at another database."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(url or get_settings().database_url, pool_pre_ping=True)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()
