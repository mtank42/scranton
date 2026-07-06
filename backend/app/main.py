"""FastAPI application factory.

Run locally:      uvicorn backend.app.main:app --reload
Interactive docs: http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.adapters.llm.factory import build_llm
from backend.app.adapters.vectorstore.chroma import ChromaStore
from backend.app.api.v1 import (
    angela,
    config,
    dwight,
    health,
    ingest,
    mood,
    pam,
    summaries,
    team,
    toby,
)
from backend.app.config import REPO_ROOT, get_settings
from backend.app.db.init_db import init_db
from backend.app.db.session import build_engine, build_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the shared adapters once, before serving.

    Everything physical (database, LLM provider, vector store) is created
    here from settings and parked on app.state: routes assemble services
    from these seams (api/deps.py) and never build adapters themselves.
    """
    settings = get_settings()
    engine = build_engine(settings.database_url)
    init_db(engine)
    app.state.session_factory = build_session_factory(engine)
    app.state.llm = build_llm(settings)
    app.state.vector_store = ChromaStore(persist_dir=settings.chroma_dir)
    yield
    engine.dispose()


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
        version="0.7.0",
        lifespan=lifespan,
    )
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(dwight.router, prefix="/api/v1")
    app.include_router(pam.router, prefix="/api/v1")
    app.include_router(mood.router, prefix="/api/v1")
    app.include_router(toby.router, prefix="/api/v1")
    app.include_router(team.router, prefix="/api/v1")
    app.include_router(summaries.router, prefix="/api/v1")
    app.include_router(angela.router, prefix="/api/v1")
    app.include_router(config.router, prefix="/api/v1")
    app.include_router(ingest.router, prefix="/api/v1")
    # The UI, served by the same process (no build tooling, no second
    # server). Mounted last: API routes always win over static files.
    app.mount(
        "/",
        StaticFiles(directory=str(REPO_ROOT / "frontend"), html=True),
        name="frontend",
    )
    return app


app = create_app()
