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

# --- Summary templates as Pam answers (recadrage 2026-07-12) ---


class StubSummaryService:
    """Records what Pam asked for and returns a canned SummaryResponse."""

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def generate(self, template_id, target_id=None, *, cold_only=False):
        from datetime import datetime, timezone

        from backend.app.domain.schemas import SummaryResponse, SummarySection

        self.calls.append((template_id, target_id, cold_only))
        if self.fail:
            raise RuntimeError("template hiccup")
        return SummaryResponse(
            template_id=template_id,
            title="Client",
            target_label="Stone & Son",
            generated_at=datetime.now(timezone.utc),
            window_days=None,
            sections=[SummarySection(heading="Commitments", content="A quote by Friday.")],
            sources=[],
        )


def seed_entities(session_factory):
    """One member, one project, one client for the closed-world router."""
    from backend.app.domain.models import Client, Project, TeamMember

    with session_factory() as session:
        member = TeamMember(full_name="Kevin")
        project = Project(name="Tables mairie")
        client = Client(name="Stone & Son")
        session.add_all([member, project, client])
        session.commit()
        return member.id, project.id, client.id


def test_broad_question_on_one_entity_serves_the_template(session_factory):
    """'Le point sur <client>' answers with the Client template, no RAG."""
    _, _, client_id = seed_entities(session_factory)
    service, llm, store = make_service(session_factory, hits=[], completions=[])
    stub = StubSummaryService()
    service.summary_service = stub

    answer = service.query("Fais-moi le point sur Stone & Son")

    # cold_only: Pam never surfaces the warm layer (owner, QA 2026-07-14).
    assert stub.calls == [("client_file", client_id, True)]
    assert answer.summary is not None
    assert answer.summary.template_id == "client_file"
    assert "Stone & Son" in answer.answer
    # The template path never touches the index or the chat model.
    assert store.query_calls == []
    assert llm.complete_calls == []
    assert llm.embed_calls == []


def test_people_are_never_served_by_pam(session_factory):
    """'Tout savoir sur Kevin' is Toby/Desk territory: RAG path, no template
    (owner, QA 2026-07-14). Projects still get their template."""
    member_id, project_id, _ = seed_entities(session_factory)
    service, _, store = make_service(session_factory, hits=[], completions=[])
    stub = StubSummaryService()
    service.summary_service = stub

    member_answer = service.query("Tout savoir sur Kevin")
    service.query("Where do we stand on Tables mairie?")

    assert member_answer.summary is None
    assert stub.calls == [("project_file", project_id, True)]
    assert len(store.query_calls) == 1  # only the member question hit retrieval


def test_pam_retrieval_is_cold_only(session_factory):
    """The Q&A path filters the index to cold segments: the warm layer
    about people belongs to Toby and the Desk (owner, QA 2026-07-14)."""
    warm_id, _ = seed_segments(session_factory)
    service, _, store = make_service(
        session_factory, hits=[hit(warm_id, 0.9)], completions=["ok [1]"]
    )

    service.query("Une question precise quelconque")

    assert store.query_calls[0]["filters"] == {"data_type": "cold"}


def test_precise_question_stays_on_the_rag_path(session_factory):
    """Naming an entity without broad intent keeps the grounded Q&A."""
    seed_entities(session_factory)
    warm_id, _ = seed_segments(session_factory)
    service, llm, store = make_service(
        session_factory,
        hits=[hit(warm_id, 0.9)],
        completions=["Kevin asked to talk [1]."],
    )
    service.summary_service = StubSummaryService()

    answer = service.query("Quand est-ce que Kevin a demandé à me parler ?")

    assert answer.summary is None
    assert store.query_calls  # retrieval ran: the RAG path answered


def test_ambiguous_or_unknown_entities_fall_back_to_rag(session_factory):
    """Two names (or none) in a broad question: no template guessing."""
    seed_entities(session_factory)
    service, _, store = make_service(
        session_factory, hits=[], completions=[]
    )
    stub = StubSummaryService()
    service.summary_service = stub

    two = service.query("Le point sur Tables mairie et Stone & Son")
    none = service.query("Le point sur la Michael Scott Paper Company")

    assert stub.calls == []
    assert two.summary is None and none.summary is None
    assert len(store.query_calls) == 2  # both went to retrieval


def test_template_failure_falls_back_to_rag(session_factory):
    """A template hiccup must never block an answer."""
    seed_entities(session_factory)
    service, _, store = make_service(session_factory, hits=[], completions=[])
    service.summary_service = StubSummaryService(fail=True)

    answer = service.query("Le point sur Stone & Son")

    assert answer.summary is None
    assert answer.answer == NO_MEMORY_ANSWER  # empty index: honest empty
    assert len(store.query_calls) == 1
