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
        self.deleted: list[int] = []
        self.hits = hits or []
        self.query_calls: list[dict] = []

    def upsert(self, segments: list[SegmentVector]) -> None:
        """Record what the pipeline tried to index."""
        self.upserted.extend(segments)

    def delete(self, ids: list[int]) -> None:
        """Record what the pipeline tried to remove from the index."""
        self.deleted.extend(ids)

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


# The manager credentials every API test runs under (identity session,
# lot 2: the API is behind auth, so the default client logs in once).
MANAGER_EMAIL = "manager@test.local"
MANAGER_PASSWORD = "test-password-123"


@pytest.fixture
def client(app):
    """HTTP client logged in as the manager (lifespan runs on enter).

    The API is behind authentication since the identity session: this
    fixture runs the first-run setup and keeps the session cookie, so
    every existing test exercises its route as the manager instead of
    re-implementing login. Anonymous behavior is tested through
    anon_client.
    """
    with TestClient(app) as test_client:
        test_client.post(
            "/api/v1/auth/setup",
            json={
                "email": MANAGER_EMAIL,
                "password": MANAGER_PASSWORD,
                "full_name": "Test Manager",
            },
        )
        yield test_client


@pytest.fixture
def anon_client(app):
    """HTTP client with no session: the outside world's view of the API."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def member_login(app, client):
    """Factory: a roster member with an account, logged in.

    Returns (client, member_id) for a freshly created member. Depends
    on the manager client so the lifespan (and the schema) exist; the
    extra TestClient shares the app but keeps its own cookie jar, like
    a second browser on another desk.
    """
    from backend.app.domain.models import TeamMember, User, UserRole
    from backend.app.services.auth_service import hash_password

    def make(name: str = "Pam", password: str = "pretzelday99"):
        email = f"{name.lower()}@test.local"
        with app.state.session_factory() as session:
            member = TeamMember(full_name=name, role="Office administrator")
            session.add(member)
            session.flush()
            session.add(
                User(
                    email=email,
                    password_hash=hash_password(password),
                    role=UserRole.MEMBER,
                    team_member_id=member.id,
                )
            )
            session.commit()
            member_id = member.id
        member_client = TestClient(app)
        response = member_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200
        return member_client, member_id

    return make
