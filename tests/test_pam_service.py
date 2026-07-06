"""The Ask Pam pipeline, tested against scripted retrieval and model.

Tests script what the index 'finds' and what the model 'answers', then
assert on grounding: context content, source order, honesty on empty.
"""

from backend.app.adapters.vectorstore.base import Hit
from backend.app.domain.models import DataType, Entry, EntrySegment, SourceType
from backend.app.services.pam_service import NO_MEMORY_ANSWER, PamService
from tests.conftest import FakeVectorStore, ScriptedLLMProvider


def seed_segments(session_factory) -> list[int]:
    """Insert one entry with two validated-in-spirit segments, return ids."""
    with session_factory() as session:
        entry = Entry(raw_content="raw note", source_type=SourceType.NOTE)
        session.add(entry)
        session.flush()
        segments = [
            EntrySegment(
                entry_id=entry.id,
                content="Kevin asked to talk: follow up on Monday.",
                segment_order=0,
                data_type=DataType.WARM,
                sensitivity_level=3,
            ),
            EntrySegment(
                entry_id=entry.id,
                content="Town hall tables delivery confirmed for Thursday.",
                segment_order=1,
                data_type=DataType.COLD,
                sensitivity_level=1,
            ),
        ]
        session.add_all(segments)
        session.commit()
        return [segment.id for segment in segments]


def hit(segment_id: int, score: float) -> Hit:
    """A minimal retrieval hit."""
    return Hit(segment_id=segment_id, score=score, metadata={})


def make_service(session_factory, hits: list[Hit], completions: list[str]):
    """Assemble a PamService on scripted fakes, returning all three."""
    llm = ScriptedLLMProvider(completions)
    store = FakeVectorStore(hits=hits)
    return PamService(llm=llm, session_factory=session_factory, vector_store=store), llm, store


def test_query_grounds_the_answer_in_retrieved_segments(session_factory):
    """Nominal path: context holds the segment texts, sources keep hit order."""
    warm_id, cold_id = seed_segments(session_factory)
    service, llm, store = make_service(
        session_factory,
        hits=[hit(warm_id, 0.92), hit(cold_id, 0.55)],
        completions=["Kevin wanted to talk to you [1]."],
    )

    result = service.query("What did Kevin want?")

    assert result.answer == "Kevin wanted to talk to you [1]."
    assert [source.segment_id for source in result.sources] == [warm_id, cold_id]
    assert result.sources[0].score == 0.92
    assert result.sources[0].data_type == DataType.WARM
    # The prompt received the numbered excerpts, content read from SQLite.
    context = llm.complete_calls[0][-1]["content"]
    assert "[1]" in context and "Kevin asked to talk" in context
    assert "[2]" in context and "tables delivery" in context
    # The question itself was embedded for retrieval.
    assert llm.embed_calls == [["What did Kevin want?"]]


def test_empty_retrieval_answers_honestly_without_a_model_call(session_factory):
    """No hits: fixed honest answer, zero completion tokens spent."""
    service, llm, store = make_service(session_factory, hits=[], completions=[])

    result = service.query("What about the Bergerac client?")

    assert result.answer == NO_MEMORY_ANSWER
    assert result.sources == []
    assert llm.complete_calls == []


def test_ghost_hits_are_treated_as_empty(session_factory):
    """Hits pointing at ids SQLite does not have must not reach the model."""
    service, llm, store = make_service(
        session_factory, hits=[hit(999, 0.9)], completions=[]
    )

    result = service.query("Anything?")

    assert result.answer == NO_MEMORY_ANSWER
    assert llm.complete_calls == []


def test_missing_segments_are_skipped_but_valid_ones_survive(session_factory):
    """A partially stale index degrades gracefully, order preserved."""
    warm_id, _ = seed_segments(session_factory)
    service, llm, store = make_service(
        session_factory,
        hits=[hit(999, 0.95), hit(warm_id, 0.80)],
        completions=["Answer [1]."],
    )

    result = service.query("What did Kevin want?")

    assert [source.segment_id for source in result.sources] == [warm_id]