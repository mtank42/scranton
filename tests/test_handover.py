"""Transfer to Philly case 1: the dossier, the fiche, the guarantees.

Everything here is deterministic - no scripted LLM anywhere, because
the handover pipeline has no LLM by design (verbatim GDPR artifact).
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.adapters.export.handover import render_html, render_markdown
from backend.app.domain.models import (
    Client,
    DataType,
    EntityType,
    Entry,
    EntrySegment,
    MoodCheckin,
    MoodLevel,
    ProposedBy,
    SegmentTag,
    SourceType,
    TeamMember,
    ValidationStatus,
)
from backend.app.services.handover_service import HandoverService
from backend.app.services.mood_service import MemberNotFoundError


def utc_naive(days_ago: int) -> datetime:
    """Naive-UTC timestamp in the past (SQLite storage format)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)


def seed_handover_case(session_factory) -> dict:
    """Kevin with a full mix: cold, warm at three sensitivities, noise.

    Noise = a proposed (unvalidated) warm segment, a segment about
    another member, member-owned profile data and mood check-ins: none
    of it may ever reach the dossier.
    """
    with session_factory() as session:
        kevin = TeamMember(
            full_name="Kevin",
            role="Senior carpenter",
            birthday=date(2000, 2, 11),
            personal_profile="Fan of New Order. Secret chili recipe.",
        )
        other = TeamMember(full_name="Thomas")
        client = Client(name="Prince Family Paper")
        session.add_all([kevin, other, client])
        session.flush()

        def segment(content, *, warm, sensitivity, days_ago, member, validated=True,
                    client_id=None):
            entry = Entry(raw_content=content, source_type=SourceType.NOTE)
            session.add(entry)
            session.flush()
            row = EntrySegment(
                entry_id=entry.id,
                content=content,
                segment_order=0,
                data_type=DataType.WARM if warm else DataType.COLD,
                sensitivity_level=sensitivity,
                validation_status=(
                    ValidationStatus.VALIDATED if validated else ValidationStatus.PROPOSED
                ),
                created_at=utc_naive(days_ago),
            )
            session.add(row)
            session.flush()
            session.add(SegmentTag(segment_id=row.id, entity_type=EntityType.TEAM_MEMBER,
                                   entity_id=member, proposed_by=ProposedBy.DWIGHT,
                                   confidence=0.9))
            if client_id:
                session.add(SegmentTag(segment_id=row.id, entity_type=EntityType.CLIENT,
                                       entity_id=client_id, proposed_by=ProposedBy.DWIGHT,
                                       confidence=0.9))
            return row

        cold = segment("Finished the <Dubreuil> kitchen two days early.",
                       warm=False, sensitivity=1, days_ago=30, member=kevin.id,
                       client_id=client.id)
        warm_mild = segment("Prefers working alone in the morning.",
                            warm=True, sensitivity=2, days_ago=20, member=kevin.id)
        warm_high = segment("Mentioned a job interview elsewhere.",
                            warm=True, sensitivity=5, days_ago=5, member=kevin.id)
        warm_mid = segment("Seemed frustrated after the delivery incident.",
                           warm=True, sensitivity=3, days_ago=10, member=kevin.id)
        segment("Proposed noise, never validated.", warm=True, sensitivity=4,
                days_ago=2, member=kevin.id, validated=False)
        segment("About Thomas, not Kevin.", warm=True, sensitivity=2,
                days_ago=3, member=other.id)
        session.add(MoodCheckin(team_member_id=kevin.id, mood_level=MoodLevel.STUCK,
                                note="private mood note", created_at=utc_naive(1)))
        session.commit()
        return {
            "kevin": kevin.id,
            "cold": cold.id,
            "warm_mild": warm_mild.id,
            "warm_mid": warm_mid.id,
            "warm_high": warm_high.id,
        }


def test_dossier_splits_cold_and_sorts_warm_by_sensitivity(session_factory):
    """Cold on one side, warm sensitivity-ascending, noise excluded."""
    ids = seed_handover_case(session_factory)
    dossier = HandoverService(session_factory).dossier(ids["kevin"])

    assert [item.segment_id for item in dossier.cold] == [ids["cold"]]
    assert [item.segment_id for item in dossier.warm] == [
        ids["warm_mild"], ids["warm_mid"], ids["warm_high"]
    ]
    assert dossier.excluded_warm_count == 0
    assert dossier.schema_id == "scranton.handover.member"
    assert dossier.schema_version == 1
    # Topics resolved to human-readable labels for the receiving side.
    assert "client: Prince Family Paper" in dossier.cold[0].topics


def test_member_owned_data_never_leaks(session_factory):
    """The profile, the birthday and the moods stay out - structurally."""
    ids = seed_handover_case(session_factory)
    dossier = HandoverService(session_factory).dossier(ids["kevin"])

    dump = dossier.model_dump_json()
    assert "New Order" not in dump
    assert "chili" not in dump
    assert "02-11" not in dump
    assert "private mood note" not in dump
    assert "stuck" not in dump


def test_selective_disclosure_counts_the_withheld(session_factory):
    """The manager's selection travels; the rest becomes a count."""
    ids = seed_handover_case(session_factory)
    service = HandoverService(session_factory)

    partial = service.dossier(ids["kevin"], include_warm=[ids["warm_mild"]])
    assert [item.segment_id for item in partial.warm] == [ids["warm_mild"]]
    assert partial.excluded_warm_count == 2

    # Empty list = disclose nothing: distinct from the review state.
    none_disclosed = service.dossier(ids["kevin"], include_warm=[])
    assert none_disclosed.warm == []
    assert none_disclosed.excluded_warm_count == 3
    # Cold is never filtered by the selection.
    assert len(none_disclosed.cold) == 1


def test_unknown_member_fails_cleanly(session_factory):
    """404 material."""
    with pytest.raises(MemberNotFoundError):
        HandoverService(session_factory).dossier(999)


def test_markdown_fiche_is_verbatim_and_signable(session_factory):
    """Exact segment text, withheld count, two signature lines."""
    ids = seed_handover_case(session_factory)
    dossier = HandoverService(session_factory).dossier(
        ids["kevin"], include_warm=[ids["warm_mild"]]
    )

    file = render_markdown(dossier)
    text = file.content.decode()

    assert file.filename.startswith("scranton_handover_kevin_")
    assert "Finished the <Dubreuil> kitchen two days early." in text  # verbatim
    assert "Prefers working alone in the morning." in text
    assert "Mentioned a job interview elsewhere." not in text  # withheld
    assert "2 observation(s) withheld" in text
    assert "Outgoing manager: ____" in text
    assert "Team member:      ____" in text


def test_html_fiche_escapes_everything(session_factory):
    """Segment text never becomes markup in the printable page."""
    ids = seed_handover_case(session_factory)
    dossier = HandoverService(session_factory).dossier(ids["kevin"])

    html = render_html(dossier).content.decode()

    assert "&lt;Dubreuil&gt;" in html
    assert "<Dubreuil>" not in html.split("</style>")[1]
    assert 'class="sign-line"' in html


def test_handover_endpoints(app, client):
    """Review vs disclosure on the wire, download headers, error codes."""
    ids = seed_handover_case(app.state.session_factory)

    review = client.get(f"/api/v1/handover/{ids['kevin']}")
    assert review.status_code == 200
    assert len(review.json()["warm"]) == 3

    # 'Disclose nothing' IS expressible: one comma-param, empty value.
    silent = client.get(f"/api/v1/handover/{ids['kevin']}", params={"include_warm": ""})
    assert silent.json()["warm"] == []
    assert silent.json()["excluded_warm_count"] == 3

    chosen = client.get(
        f"/api/v1/handover/{ids['kevin']}",
        params={"include_warm": str(ids["warm_high"])},
    )
    assert [item["segment_id"] for item in chosen.json()["warm"]] == [ids["warm_high"]]

    export = client.get(
        f"/api/v1/handover/{ids['kevin']}/export",
        params={"format": "md", "include_warm": "none"},
    )
    assert export.status_code == 200
    assert "attachment" in export.headers["content-disposition"]
    assert "3 observation(s) withheld" in export.text

    assert client.get("/api/v1/handover/999").status_code == 404
    assert (
        client.get(f"/api/v1/handover/{ids['kevin']}/export", params={"format": "pdf"})
        .status_code == 422
    )
    assert (
        client.get(f"/api/v1/handover/{ids['kevin']}", params={"include_warm": "abc"})
        .status_code == 422
    )