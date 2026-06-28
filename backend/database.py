"""Database setup using SQLModel.

Defaults to a local SQLite file; in production set DATABASE_URL (e.g. an absolute
SQLite path on a mounted disk: sqlite:////var/data/newsletters.db). Tables are
created automatically on startup.
"""

import os

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///newsletters.db")
_IS_SQLITE = DATABASE_URL.startswith("sqlite")

# check_same_thread=False lets FastAPI's threadpool share a SQLite connection.
_connect_args = {"check_same_thread": False} if _IS_SQLITE else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)


def init_db() -> None:
    """Create tables on startup and apply tiny in-place migrations."""
    # Import models so they register on SQLModel.metadata before create_all.
    from models.db import (  # noqa: F401
        FilterPreset,
        SavedNewsletter,
        Subscription,
        Topic,
        User,
    )

    SQLModel.metadata.create_all(engine)
    # The lightweight migrations below use SQLite-specific PRAGMA/ALTER syntax.
    # On other engines a fresh create_all already has the current schema.
    if _IS_SQLITE:
        _add_missing_columns()
        _drop_legacy_topic_unique_index()


def _add_missing_columns() -> None:
    """Add columns introduced after a DB was first created.

    SQLModel's create_all never alters existing tables, so a database from an
    earlier version is missing newer columns. We add them with plain ALTER TABLE
    (idempotent — only runs when the column is absent).
    """
    additions = {
        "savednewsletter": {
            "from_date": "DATE",
            "to_date": "DATE",
            "user_id": "INTEGER",
            "subject_options": "JSON DEFAULT '[]'",
            "preview_text": "TEXT",
            "filters": "JSON DEFAULT '{}'",
        },
        "topic": {"user_id": "INTEGER"},
        "subscription": {"recipients": "JSON DEFAULT '[]'"},
    }
    with engine.begin() as conn:
        for table, columns in additions.items():
            existing = {
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))
            }
            for name, coltype in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}"))


def _drop_legacy_topic_unique_index() -> None:
    """Topic.name used to be globally unique; now it's unique per-user (enforced
    in app code). Drop any leftover unique index so two users can share a name."""
    with engine.begin() as conn:
        for row in conn.execute(text("PRAGMA index_list(topic)")):
            name, is_unique = row[1], row[2]
            if is_unique and name.startswith("ix_"):
                conn.execute(text(f"DROP INDEX IF EXISTS {name}"))


def get_session():
    """FastAPI dependency that yields a database session per request."""
    with Session(engine) as session:
        yield session
