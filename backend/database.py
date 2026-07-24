"""SQLAlchemy engine, session factory and declarative base.

Sync SQLAlchemy 2.0. Route handlers that touch the DB are defined as `def`
(FastAPI runs them in a threadpool), keeping the data layer simple.
"""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _build_engine():
    url = settings.database_url
    connect_args: dict = {}

    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # Ensure the parent directory exists for file-based SQLite URLs.
        # sqlite:///relative/path.db  or  sqlite:////absolute/path.db
        path = url.split("sqlite:///", 1)[-1]
        if path and path not in (":memory:",):
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)

    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
