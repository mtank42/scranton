"""Integration smoke tests against the real Mistral API.

Excluded from the default run (pytest.ini). Run explicitly with:
    pytest -m integration

These only prove the wiring (auth, request shape, response parsing):
quality evaluation of the Dwight prompt is a separate, manual exercise.
"""

import os

import pytest

from backend.app.adapters.llm.mistral import MistralProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("MISTRAL_API_KEY"), reason="MISTRAL_API_KEY not set"
    ),
]


@pytest.fixture
def provider() -> MistralProvider:
    """A real provider built from the local .env key."""
    return MistralProvider(api_key=os.environ["MISTRAL_API_KEY"])


def test_complete_answers(provider):
    """One tiny completion proves auth and response parsing."""
    answer = provider.complete(
        [{"role": "user", "content": "Reply with the single word: pretzel"}]
    )
    assert "pretzel" in answer.lower()


def test_embed_returns_one_vector_per_text(provider):
    """Embeddings come back aligned with the inputs and non-trivial."""
    vectors = provider.embed(["hello", "world"])
    assert len(vectors) == 2
    assert len(vectors[0]) > 100
