"""The Ask Pam pipeline, tested against scripted retrieval and model.

Tests script what the index 'finds' and what the model 'answers', then
assert on grounding: context content, source order, honesty on empty.
"""

from backend.app.adapters.vectorstore.base import Hit
from backend.app.domain.models import DataType, Entry, EntrySegment, SourceType
from backend.app.services.pam_service import (
    NO_MEMORY_ANSWER,
    PEOPLE_REDIRECT_ANSWER,
    PamService,
)
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
    """Nominal path: context holds the segment texts, cited sources
    come back with their excerpt number (ref) intact."""
    warm_id, cold_id = seed_segments(session_factory)
    service, llm, store = make_service(
        session_factory,
        hits=[hit(warm_id, 0.92), hit(cold_id, 0.75)],
        completions=["Kevin wanted to talk to you [1]."],
    )

    result = service.query("What did Kevin want?")

    assert result.answer == "Kevin wanted to talk to you [1]."
    # Only the cited excerpt survives as a source (QA 2026-07-14: the
    # uncited rest of top-k was pure noise), numbering preserved.
    assert [source.segment_id for source in result.sources] == [warm_id]
    assert result.sources[0].ref == 1
    assert result.sources[0].score == 0.92
    assert result.sources[0].data_type == DataType.WARM
    # The prompt received ALL retained excerpts, content read from SQLite.
    context = llm.complete_calls[0][-1]["content"]
    assert "[1]" in context and "Kevin asked to talk" in context
    assert "[2]" in context and "tables delivery" in context
    # The question itself was embedded for retrieval.
    assert llm.embed_calls == [["What did Kevin want?"]]


def test_low_similarity_hits_are_dropped_before_the_model(session_factory):
    """The retrieval floor: a far-fetched hit never reaches the context."""
    warm_id, cold_id = seed_segments(session_factory)
    service, llm, store = make_service(
        session_factory,
        hits=[hit(warm_id, 0.9), hit(cold_id, 0.3)],
        completions=["Answer [1]."],
    )

    result = service.query("What did Kevin want?")

    context = llm.complete_calls[0][-1]["content"]
    assert "tables delivery" not in context
    assert [source.segment_id for source in result.sources] == [warm_id]


def test_all_hits_below_the_floor_answer_honestly_for_free(session_factory):
    """Nothing relevant enough: honest empty, zero completion tokens."""
    warm_id, cold_id = seed_segments(session_factory)
    service, llm, store = make_service(
        session_factory,
        hits=[hit(warm_id, 0.42), hit(cold_id, 0.31)],
        completions=[],
    )

    result = service.query("Anything on the Bergerac account?")

    assert result.answer == NO_MEMORY_ANSWER
    assert result.sources == []
    assert llm.complete_calls == []


def test_uncited_sources_are_dropped_but_keep_their_number(session_factory):
    """Citing [2] only: source [2] survives, still numbered 2."""
    warm_id, cold_id = seed_segments(session_factory)
    service, _, _ = make_service(
        session_factory,
        hits=[hit(warm_id, 0.9), hit(cold_id, 0.8)],
        completions=["The delivery is confirmed for Thursday [2]."],
    )

    result = service.query("When is the tables delivery?")

    assert [source.segment_id for source in result.sources] == [cold_id]
    assert result.sources[0].ref == 2


def test_answer_without_citations_shows_no_sources(session_factory):
    """Prompt rule 3: unrelated excerpts get an honest empty and no
    source list - showing them anyway was the QA's noise complaint."""
    warm_id, _ = seed_segments(session_factory)
    service, _, _ = make_service(
        session_factory,
        hits=[hit(warm_id, 0.9)],
        completions=["The memory holds nothing about the Bergerac account."],
    )

    result = service.query("What about the Bergerac client?")

    assert result.sources == []


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


def test_one_member_broad_question_gets_the_redirect(session_factory):
    """'Tout savoir sur Kevin' is Toby/Desk territory: deterministic
    redirect, no template, no retrieval, zero sources (owner, QA
    2026-07-14: the old RAG fallback served 10 unrelated sources).
    Projects still get their template."""
    member_id, project_id, _ = seed_entities(session_factory)
    service, llm, store = make_service(session_factory, hits=[], completions=[])
    stub = StubSummaryService()
    service.summary_service = stub

    member_answer = service.query("Tout savoir sur Kevin")
    service.query("Where do we stand on Tables mairie?")

    assert member_answer.answer == PEOPLE_REDIRECT_ANSWER
    assert member_answer.summary is None
    assert member_answer.sources == []
    assert stub.calls == [("project_file", project_id, True)]
    assert store.query_calls == []  # neither question hit retrieval
    assert llm.complete_calls == [] and llm.embed_calls == []


def seed_shared_work(session_factory):
    """Two members, one shared client, one project of Kevin's own."""
    from backend.app.domain.models import (
        Client,
        Entry,
        EntityType,
        Project,
        ProposedBy,
        SegmentTag,
        SourceType,
        TeamMember,
        ValidationStatus,
    )

    with session_factory() as session:
        kevin = TeamMember(full_name="Kevin")
        holly = TeamMember(full_name="Holly")
        client = Client(name="Vance Refrigeration")
        project = Project(name="Warehouse racks")
        session.add_all([kevin, holly, client, project])
        session.flush()
        entry = Entry(raw_content="raw", source_type=SourceType.NOTE)
        session.add(entry)
        session.flush()

        def add_segment(content, data_type, status, tags):
            segment = EntrySegment(
                entry_id=entry.id,
                content=content,
                segment_order=0,
                data_type=data_type,
                sensitivity_level=1,
                validation_status=status,
            )
            session.add(segment)
            session.flush()
            for entity_type, entity_id in tags:
                session.add(
                    SegmentTag(
                        segment_id=segment.id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        proposed_by=ProposedBy.DWIGHT,
                        confidence=0.9,
                        validated=status == ValidationStatus.VALIDATED,
                    )
                )
            return segment.id

        # Both members tagged with the client on validated cold segments.
        kevin_seg = add_segment(
            "Kevin handled the Vance quote.",
            DataType.COLD,
            ValidationStatus.VALIDATED,
            [(EntityType.TEAM_MEMBER, kevin.id), (EntityType.CLIENT, client.id)],
        )
        add_segment(
            "Holly closed the Vance follow-up.",
            DataType.COLD,
            ValidationStatus.VALIDATED,
            [(EntityType.TEAM_MEMBER, holly.id), (EntityType.CLIENT, client.id)],
        )
        # Kevin alone on the project: must NOT count as shared.
        add_segment(
            "Kevin drafted the racks plan.",
            DataType.COLD,
            ValidationStatus.VALIDATED,
            [(EntityType.TEAM_MEMBER, kevin.id), (EntityType.PROJECT, project.id)],
        )
        # A PROPOSED link both ways: the validation gate holds here too.
        add_segment(
            "Kevin and Holly maybe on racks.",
            DataType.COLD,
            ValidationStatus.PROPOSED,
            [
                (EntityType.TEAM_MEMBER, holly.id),
                (EntityType.PROJECT, project.id),
            ],
        )
        session.commit()
        return kevin_seg


def test_two_members_broad_question_lists_shared_work(session_factory):
    """'Le point sur Kevin et Holly': the deterministic overlap answer,
    validated links only, cold sources as receipts, no LLM."""
    kevin_seg = seed_shared_work(session_factory)
    service, llm, store = make_service(session_factory, hits=[], completions=[])

    result = service.query("Le point sur Kevin et Holly")

    assert "Kevin and Holly appear together on: Vance Refrigeration (client)" in result.answer
    # The unshared project and the proposed-only link stay out.
    assert "Warehouse racks" not in result.answer
    assert kevin_seg in {source.segment_id for source in result.sources}
    assert all(source.data_type == DataType.COLD for source in result.sources)
    assert llm.complete_calls == [] and store.query_calls == []


def test_two_members_with_no_overlap_get_an_honest_empty(session_factory):
    """No shared entity: say so, point to Toby, no sources."""
    from backend.app.domain.models import TeamMember

    with session_factory() as session:
        session.add_all([TeamMember(full_name="Angela"), TeamMember(full_name="Creed")])
        session.commit()
    service, llm, _ = make_service(session_factory, hits=[], completions=[])

    result = service.query("Le point sur Angela et Creed")

    assert "no shared project or client" in result.answer
    assert result.sources == []
    assert llm.complete_calls == []


def test_member_plus_entity_broad_question_falls_back_to_rag(session_factory):
    """A member AND a client in one broad question is a mixed picture:
    no deterministic guess, grounded RAG decides."""
    seed_entities(session_factory)
    service, _, store = make_service(session_factory, hits=[], completions=[])
    stub = StubSummaryService()
    service.summary_service = stub

    result = service.query("Le point sur Kevin et Stone & Son")

    assert result.summary is None
    assert stub.calls == []
    assert len(store.query_calls) == 1


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
