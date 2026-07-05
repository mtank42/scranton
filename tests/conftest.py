"""Shared fixtures: fake LLM provider, in-memory database, HTTP client.

Unit tests never touch the network: every model call goes through
FakeLLMProvider (deterministic, fast, free). Real provider calls become
integration smoke tests behind the 'integration' marker from M1 on.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from backend.app.adapters.llm.base import LLMProvider
from backend.app.main import create_app


class FakeLLMProvider(LLMProvider):
    """Deterministic, offline stand-in for a real provider."""

    def complete(self, messages: list[dict], *, model: str | None = None) -> str:
        """Echo the last message so assertions stay predictable."""
        return f"fake-completion: {messages[-1]['content']}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Fixed 3-float vectors: enough to test plumbing, no model needed."""
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    """A fresh fake provider for each test."""
    return FakeLLMProvider()


@pytest.fixture
def engine():
    """In-memory SQLite engine: each test gets a fresh, isolated schema."""
    engine = create_engine("sqlite:///:memory:")
    yield engine
    engine.dispose()


@pytest.fixture
def client(monkeypatch):
    """HTTP client on a fresh app instance.

    DATABASE_URL is forced to in-memory so the startup hook never writes
    a real file under data/ during a test run.
    """
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
