"""Golden Ask Pam queries over the seeded dataset (anti-regression).

The QA standard from SCRANTON_CONTEXT section 11: a fixed set of
questions with known right sources, run against the REAL provider and a
real local Chroma index. Catches regressions in the prompt, the
embeddings, the retrieval wiring, or the dataset itself.

Excluded from the default run: pytest -m integration
"""

import os

import pytest
from sqlalchemy import create_engine

from backend.app.adapters.llm.mistral import MistralProvider
from backend.app.adapters.vectorstore.chroma import ChromaStore
from backend.app.db.init_db import init_db
from backend.app.db.seed import seed
from backend.app.db.session import build_session_factory
from backend.app.services.pam_service import PamService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("MISTRAL_API_KEY"), reason="MISTRAL_API_KEY not set"
    ),
]

# (question, snippet expected in the top sources' contents)
GOLDEN = [
    ("What did we promise to Stone & Son?", "revised quote"),
    ("How is Ryan doing lately?", "exhausted"),
    ("Who owns the delivery routes overhaul?", "Val owns the new schedule"),
    ("Is there anything to know about Keystone Logistics?", "late on two deliveries"),
    ("When is the Lackawanna cardstock delivery due?", "September 15"),
]


@pytest.fixture(scope="module")
def pam(tmp_path_factory):
    """Seed once (real embeddings) into throwaway stores, serve PamService."""
    tmp_path = tmp_path_factory.mktemp("golden")
    engine = create_engine(f"sqlite:///{tmp_path / 'golden.db'}")
    init_db(engine)
    session_factory = build_session_factory(engine)
    llm = MistralProvider(api_key=os.environ["MISTRAL_API_KEY"])
    store = ChromaStore(persist_dir=str(tmp_path / "chroma"))
    message = seed(session_factory, llm, store)
    assert "Seeded" in message
    yield PamService(llm=llm, session_factory=session_factory, vector_store=store)
    engine.dispose()


@pytest.mark.parametrize("question,expected_snippet", GOLDEN)
def test_golden_query_retrieves_the_right_source(pam, question, expected_snippet):
    """The expected segment must appear in the top-3 retrieved sources.

    Deliberately asserts on RETRIEVAL (stable) rather than on the answer
    wording (model-dependent): the golden set must not flake with every
    provider update.
    """
    result = pam.query(question, k=3)
    contents = " | ".join(source.content for source in result.sources)
    assert expected_snippet in contents, (
        f"Expected snippet {expected_snippet!r} not in top-3 sources: {contents}"
    )
    assert result.answer  # and the model did produce a grounded answer