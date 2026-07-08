"""Transfer to Philly case 1: the dossier, the fiche, the guarantees.

Everything here is deterministic - no scripted LLM anywhere, because
the handover pipeline has no LLM by design (verbatim GDPR artifact).
"""

import hashlib
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.adapters.export.handover import render_html, render_markdown
from backend.app.domain.models import (
    Client,
    DataType,
    EntityType,
    Entry,
    EntrySegment,
    HandoverStatus,
    MoodCheckin,
    MoodLevel,
    ProposedBy,
    SegmentTag,
    SourceType,
    TeamMember,
    ValidationStatus,
)
from backend.app.services.handover_service import (
    ActiveHandoverExistsError,
    HandoverNotFoundError,
    HandoverService,
    InvalidSelectionError,
    InvalidTransitionError,
)
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


def test_consent_trail_happy_path(session_factory):
    """create -> review -> sign -> send, one timestamp per transition."""
    ids = seed_handover_case(session_factory)
    service = HandoverService(session_factory)

    record = service.create_validation(
        ids["kevin"], disclosed_warm_ids=[ids["warm_mild"]]
    )
    assert record.status is HandoverStatus.PROPOSED
    assert record.disclosed_warm_ids == [ids["warm_mild"]]
    assert record.fiche_sha256 is None

    record = service.mark_reviewed(record.id)
    assert record.status is HandoverStatus.EMPLOYEE_REVIEWED
    assert record.reviewed_at is not None

    record = service.sign(
        record.id, manager_name="Michael Scott", member_name="Kevin"
    )
    assert record.status is HandoverStatus.BOTH_VALIDATED
    assert record.manager_signature_name == "Michael Scott"
    assert record.member_signature_name == "Kevin"
    assert record.manager_signed_at is not None
    assert record.member_signed_at is not None
    assert record.validated_at is not None
    assert record.fiche_sha256 is not None and len(record.fiche_sha256) == 64

    record = service.mark_sent(record.id)
    assert record.status is HandoverStatus.SENT
    assert record.sent_at is not None


def test_signed_fiche_is_byte_stable_and_matches_the_hash(session_factory):
    """The download reproduces the signed bytes; hashing it verifies them."""
    ids = seed_handover_case(session_factory)
    service = HandoverService(session_factory)
    record = service.create_validation(
        ids["kevin"], disclosed_warm_ids=[ids["warm_mild"]]
    )
    service.mark_reviewed(record.id)
    record = service.sign(record.id, manager_name="Michael Scott", member_name="Kevin")

    first = service.signed_fiche(record.id, format_key="md")
    second = service.signed_fiche(record.id, format_key="md")
    assert first.content == second.content
    assert hashlib.sha256(first.content).hexdigest() == record.fiche_sha256

    text = first.content.decode()
    assert "Michael Scott" in text  # typed signature, not a blank line
    assert "______" not in text
    assert "Prefers working alone in the morning." in text  # frozen selection
    assert "Mentioned a job interview elsewhere." not in text  # withheld
    assert "2 observation(s) withheld" in text
    # The printable variant carries the signatures too.
    assert "Michael Scott" in service.signed_fiche(record.id, format_key="html").content.decode()
    # Downloading is a verification, never a transmission.
    assert service.validations(ids["kevin"])[0].status is HandoverStatus.BOTH_VALIDATED


def test_transitions_are_strictly_forward(session_factory):
    """No skipping, no repeating, no fiche before signature."""
    ids = seed_handover_case(session_factory)
    service = HandoverService(session_factory)
    record = service.create_validation(ids["kevin"], disclosed_warm_ids=[])

    with pytest.raises(InvalidTransitionError):
        service.sign(record.id, manager_name="M", member_name="K")  # skips review
    with pytest.raises(InvalidTransitionError):
        service.mark_sent(record.id)  # skips two states
    with pytest.raises(InvalidTransitionError):
        service.signed_fiche(record.id, format_key="md")  # nothing signed yet

    service.mark_reviewed(record.id)
    with pytest.raises(InvalidTransitionError):
        service.mark_reviewed(record.id)  # no state repeats

    with pytest.raises(HandoverNotFoundError):
        service.mark_reviewed(9999)


def test_selection_freezes_once_reviewed(session_factory):
    """Mutable while proposed, frozen from employee_reviewed on."""
    ids = seed_handover_case(session_factory)
    service = HandoverService(session_factory)
    record = service.create_validation(ids["kevin"], disclosed_warm_ids=[])

    record = service.update_selection(
        record.id, disclosed_warm_ids=[ids["warm_high"], ids["warm_mild"]]
    )
    assert record.disclosed_warm_ids == sorted([ids["warm_mild"], ids["warm_high"]])

    service.mark_reviewed(record.id)
    with pytest.raises(InvalidTransitionError):
        service.update_selection(record.id, disclosed_warm_ids=[])


def test_selection_only_accepts_disclosable_warm_segments(session_factory):
    """Cold ids, foreign ids and ghost members are all refused."""
    ids = seed_handover_case(session_factory)
    service = HandoverService(session_factory)

    with pytest.raises(InvalidSelectionError):
        service.create_validation(ids["kevin"], disclosed_warm_ids=[ids["cold"]])
    with pytest.raises(InvalidSelectionError):
        service.create_validation(ids["kevin"], disclosed_warm_ids=[99999])
    with pytest.raises(MemberNotFoundError):
        service.create_validation(999, disclosed_warm_ids=[])


def test_one_open_handover_per_member(session_factory):
    """A second consent thread would make 'what was agreed' ambiguous."""
    ids = seed_handover_case(session_factory)
    service = HandoverService(session_factory)
    record = service.create_validation(ids["kevin"], disclosed_warm_ids=[])

    with pytest.raises(ActiveHandoverExistsError):
        service.create_validation(ids["kevin"], disclosed_warm_ids=[])

    # A sent handover closes the thread: a new one may open.
    service.mark_reviewed(record.id)
    service.sign(record.id, manager_name="Michael Scott", member_name="Kevin")
    service.mark_sent(record.id)
    second = service.create_validation(ids["kevin"], disclosed_warm_ids=[])
    assert second.id != record.id
    assert [v.id for v in service.validations(ids["kevin"])] == [second.id, record.id]


def test_consent_trail_endpoints(app, client):
    """The full workflow on the wire, plus the error contract."""
    ids = seed_handover_case(app.state.session_factory)
    kevin = ids["kevin"]

    created = client.post(
        f"/api/v1/handover/{kevin}/validations",
        json={"disclosed_warm_ids": [ids["warm_mild"]]},
    )
    assert created.status_code == 200
    vid = created.json()["id"]
    assert created.json()["status"] == "proposed"

    # One open handover per member.
    assert client.post(f"/api/v1/handover/{kevin}/validations", json={}).status_code == 409

    updated = client.put(
        f"/api/v1/handover/validations/{vid}/selection",
        json={"disclosed_warm_ids": [ids["warm_mid"], ids["warm_mild"]]},
    )
    assert updated.json()["disclosed_warm_ids"] == sorted(
        [ids["warm_mild"], ids["warm_mid"]]
    )
    assert (
        client.put(
            f"/api/v1/handover/validations/{vid}/selection",
            json={"disclosed_warm_ids": [ids["cold"]]},
        ).status_code
        == 422
    )

    # Nothing signable or downloadable before its state.
    assert client.get(f"/api/v1/handover/validations/{vid}/export").status_code == 409
    assert (
        client.post(
            f"/api/v1/handover/validations/{vid}/sign",
            json={"manager_name": "Michael Scott", "member_name": "Kevin"},
        ).status_code
        == 409
    )

    assert client.post(f"/api/v1/handover/validations/{vid}/review").status_code == 200
    signed = client.post(
        f"/api/v1/handover/validations/{vid}/sign",
        json={"manager_name": "Michael Scott", "member_name": "Kevin"},
    )
    assert signed.status_code == 200
    digest = signed.json()["fiche_sha256"]

    export = client.get(
        f"/api/v1/handover/validations/{vid}/export", params={"format": "md"}
    )
    assert export.status_code == 200
    assert "attachment" in export.headers["content-disposition"]
    assert hashlib.sha256(export.content).hexdigest() == digest
    assert "Michael Scott" in export.text

    # The download did NOT transmit anything: send is an explicit action.
    listing = client.get(f"/api/v1/handover/{kevin}/validations")
    assert listing.json()[0]["status"] == "both_validated"
    assert client.post(f"/api/v1/handover/validations/{vid}/send").status_code == 200
    assert (
        client.get(f"/api/v1/handover/{kevin}/validations").json()[0]["status"]
        == "sent"
    )

    # Error contract leftovers.
    assert client.get("/api/v1/handover/999/validations").status_code == 404
    assert client.post("/api/v1/handover/validations/999/review").status_code == 404
    assert (
        client.get(
            f"/api/v1/handover/validations/{vid}/export", params={"format": "pdf"}
        ).status_code
        == 422
    )


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