"""Database initialization: create the tables if missing.

Why create_all instead of Alembic migrations: the POC is single-user,
local-first, and the data model is frozen. create_all is idempotent and
sufficient; Alembic can be introduced later without rework if the schema
ever has to evolve in place.
"""

from pathlib import Path

from sqlalchemy.engine import Engine

from backend.app.domain.models import Base


def init_db(engine: Engine) -> None:
    """Create every missing table. Existing tables and data are untouched.

    Seeding the fictitious Dunder Mifflin demo dataset is a separate,
    explicit step that lands in M3 (demo preparation).
    """
    # For a file-based SQLite URL, make sure the parent directory exists:
    # a fresh clone ships data/, but a custom DATABASE_URL might point
    # somewhere that does not exist yet.
    database = engine.url.database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
