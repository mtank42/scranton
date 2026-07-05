"""SQLite engine and session factory.

The database URL always comes from settings: the same build must run on
a local disk, a NAS mount, or a cloud volume (and SQLite can later become
Postgres for multi-user) with nothing but a configuration change.
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings


def build_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the given URL, or the configured one."""
    url = database_url or get_settings().database_url
    # SQLite refuses cross-thread connections by default. FastAPI may serve
    # a request from a different thread than the one that opened the pool,
    # so we relax that check - for SQLite only.
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine.

    expire_on_commit=False keeps returned objects readable after commit,
    which makes service code and tests simpler to follow.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)
