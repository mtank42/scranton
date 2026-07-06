"""Shared fixtures: fake adapters, isolated database, HTTP client.

Unit tests never touch the network: every model call goes through a fake
provider (deterministic, fast, free). Real provider calls live in the
integration tests, excluded from the default run (see pytest.ini).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from backend.app.adapters.llm.base import LLMProvider
from backend.app.adapters.vectorstore.base import Hit, SegmentVector, VectorStore
from backend.app.db.init_db import init_db
from backend.app.db.session import build_session_factory
from backend.app.main import create_app


class FakeLLMProvider(LLMProvider):
    """Deterministic, offline stand-in for a real provider."""

    def complete(self, messages: list[dict], *, model: str | None = None) -> str:
        """Echo the last message so assertions stay predictable."""
        return f"fake-completion: {messages[-1]['content']}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Fixed 3-float vectors: enough to test plumbing, no model needed."""
        return [[0.1, 0.2, 0.3] for _ in texts]


class ScriptedLLMProvider(LLMProvider):
    """Returns pre-scripted completions in order, and records every call.

    This is how the Dwight pipeline is tested without a network: the test
    scripts exactly what 'the model' answers, then asserts on what the
    pipeline did with it.
    """

    def __init__(self, completions: list[str]) -> None:
        """Queue the answers the fake model will give, in order."""
        self.completions = list(completions)
        self.complete_calls: list[list[dict]] = []
        self.embed_calls: list[list[str]] = []

    def complete(self, messages: list[dict], *, model: str | None = None) -> str:
        """Pop and return the next scripted answer."""
        self.complete_calls.append(messages)
        return self.completions.pop(0)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Fixed 4-float vectors, with the call recorded for assertions."""
        self.embed_calls.append(list(texts))
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


class FakeVectorStore(VectorStore):
    """In-memory vector store: records upserts, returns scripted hits.

    Tests script what retrieval 'finds' (hits) the same way they script
    what the model 'answers' (ScriptedLLMProvider): the pipeline around
    the seams is what gets asserted.
    """

    def __init__(self, hits: list[Hit] | None = None) -> None:
        """Optionally queue the hits every query will return."""
        self.upserted: list[SegmentVector] = []
        self.hits = hits or []
        self.query_calls: list[dict] = []

    def upsert(self, segments: list[SegmentVector]) -> None:
        """Record what the pipeline tried to index."""
        self.upserted.extend(segments)

    def query(
        self, embedding: list[float], *, filters: dict | None = None, k: int = 8
    ) -> list[Hit]:
        """Return the scripted hits (capped at k), recording the call."""
        self.query_calls.append({"embedding": embedding, "filters": filters, "k": k})
        return self.hits[:k]


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
def session_factory(engine):
    """Session factory on an initialized in-memory schema."""
    init_db(engine)
    return build_session_factory(engine)


@pytest.fixture
def app(monkeypatch, tmp_path):
    """A fresh app instance wired to throwaway data locations.

    A file-based SQLite (not :memory:) because the TestClient may serve
    requests from another thread, and each :memory: connection would see
    its own empty database.
    """
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    return create_app()


@pytest.fixture
def client(app):
    """HTTP client on the fresh app instance (lifespan runs on enter)."""
    with TestClient(app) as test_client:
        yield test_client
