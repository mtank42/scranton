"""FastAPI application factory.

Run locally:      uvicorn backend.app.main:app --reload
Interactive docs: http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.v1 import health
from backend.app.db.init_db import init_db
from backend.app.db.session import build_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup hook: make sure the SQLite schema exists before serving."""
    init_db(build_engine())
    yield


def create_app() -> FastAPI:
    """Build the application.

    A factory (instead of an app built inline at module level) lets tests
    create fresh, isolated instances with their own configuration.
    """
    app = FastAPI(
        title="Scranton",
        description=(
            "A managerial OS for proximity managers: "
            "one smart notepad, zero bureaucracy, 100% team."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
