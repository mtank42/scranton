"""Demo dataset: the fictitious Dunder Mifflin team, ~3 months of history.

Deterministic on purpose: segments are pre-written (no LLM call decides
the data), so the demo is reproducible and the golden queries have known
right answers. The only real model calls are the embeddings of validated
segments, made once at seed time.

The storylines are demo material:
- Ryan's mood declines over the quarter (ctrl -> press -> stuck ->
  danger) with two sensitive warm segments: the act-at-week-6 story.
- Darryl stops checking in: the silence signal.
- Two segments are left unvalidated: live material for the validation UI.

Run:  python -m backend.app.db.seed [--reset]
"""

import argparse
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.llm.base import LLMProvider
from backend.app.adapters.llm.factory import build_llm
from backend.app.adapters.vectorstore.base import SegmentVector, VectorStore
from backend.app.adapters.vectorstore.chroma import ChromaStore
from backend.app.config import get_settings
from backend.app.db.init_db import init_db
from backend.app.db.session import build_engine, build_session_factory
from backend.app.domain.models import (
    Client,
    DataType,
    EntityType,
    Entry,
    EntrySegment,
    MoodCheckin,
    MoodLevel,
    ProcessingStatus,
    Project,
    ProposedBy,
    RelationshipType,
    SegmentTag,
    SourceType,
    Stakeholder,
    TeamMember,
    ValidationStatus,
    ViewType,
)
from backend.app.services.dwight_service import flatten_segment_metadata


def days_ago(days: int) -> datetime:
    """Naive-UTC timestamp 'days' in the past (how SQLite stores our dates)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)


# --- The dataset (names reserved for fictitious users, SCRANTON_CONTEXT §3) ---

TEAM = [
    ("Ryan", "Junior salesman"),
    ("Oscar", "Accountant"),
    ("Kelly", "Customer service"),
    ("Phyllis", "Saleswoman"),
    ("Stanley", "Salesman"),
    ("Darryl", "Warehouse foreman"),
]

# Member-owned data (human profile). Sparse on purpose: profiles grow
# from real conversations, they are not an HR form to fill.
PROFILES: dict[str, dict] = {
    "Kelly": {
        "birthday": "1990-02-14",
        "personal_profile": "Loves romantic comedies and celebrity news. Collects lip gloss.",
    },
    "Darryl": {
        "birthday": "1978-10-01",
        "personal_profile": "Plays keyboard in a band. Chess player. Dreams of running his own business.",
    },
}

CLIENTS = ["Lackawanna County Schools", "Stone & Son Suit Warehouse", "Prince Family Paper"]

PROJECTS = [
    ("Q3 cardstock contract", "Lackawanna County Schools"),
    ("Delivery routes overhaul", None),
]

STAKEHOLDERS = [
    ("Scranton Business Park", RelationshipType.INSTITUTIONAL),
    ("Keystone Logistics", RelationshipType.SUBCONTRACTOR),
]

# One entry per segment: (days_ago, raw_content, content, data_type,
# sensitivity, validated, tags). Tags reference entities BY NAME; ids are
# resolved at insert time. ("view", view_type) routes to a view.
SEGMENTS = [
    (80, "lackawanna confirmed q3 cardstock 200 boxes sept 15",
     "Lackawanna County Schools confirmed the Q3 cardstock order: 200 boxes, delivery by September 15.",
     DataType.COLD, 1, True,
     [("client", "Lackawanna County Schools"), ("project", "Q3 cardstock contract"), ("view", ViewType.COMMITMENT)]),
    (75, "ryan distracted in sales meeting, asked twice about commissions",
     "Ryan seemed distracted during the sales meeting; he asked twice about the commission structure.",
     DataType.WARM, 3, True,
     [("team_member", "Ryan"), ("view", ViewType.TEAM_MEMBER_FILE)]),
    (70, "stanley wants written briefs not morning meetings",
     "Stanley prefers written briefs over morning meetings; agreed to send him the summary by email.",
     DataType.COLD, 2, True,
     [("team_member", "Stanley")]),
    (65, "stone and son quote letterhead, follow up tuesday",
     "Stone & Son asked for a quote on letterhead paper; follow-up call next Tuesday.",
     DataType.COLD, 1, True,
     [("client", "Stone & Son Suit Warehouse"), ("view", ViewType.MEETING_AGENDA)]),
    (60, "kelly handled prince family complaint great, client called to thank",
     "Kelly handled the Prince Family Paper complaint remarkably well; the client called back to thank us.",
     DataType.WARM, 2, True,
     [("team_member", "Kelly"), ("client", "Prince Family Paper")]),
    (50, "keystone late twice this month, flagged to account manager",
     "Keystone Logistics was late on two deliveries this month; flagged to their account manager.",
     DataType.COLD, 2, True,
     [("stakeholder", "Keystone Logistics")]),
    (40, "routes overhaul kickoff darryl owns schedule draft in 2 weeks",
     "Delivery routes overhaul kickoff: Darryl owns the new schedule, first draft expected in two weeks.",
     DataType.COLD, 1, True,
     [("team_member", "Darryl"), ("project", "Delivery routes overhaul"), ("view", ViewType.PROJECT_FILE)]),
    (35, "phyllis mentored ryan on cold calls, keep it quiet",
     "Phyllis quietly mentored Ryan on cold calls this week; she did not want it mentioned in the meeting.",
     DataType.WARM, 3, True,
     [("team_member", "Phyllis"), ("team_member", "Ryan")]),
    (30, "oscar found recurring invoicing error on lackawanna",
     "Oscar flagged a recurring invoicing error on the Lackawanna account; fix agreed with accounting.",
     DataType.COLD, 2, True,
     [("team_member", "Oscar"), ("client", "Lackawanna County Schools")]),
    (20, "ryan exhausted, wonders if sales is right for him",
     "Ryan mentioned he is exhausted and wonders if sales is the right fit for him.",
     DataType.WARM, 4, True,
     [("team_member", "Ryan"), ("view", ViewType.TEAM_MEMBER_FILE)]),
    (15, "promised stone and son revised quote before end of month",
     "Promised Stone & Son a revised quote before the end of the month.",
     DataType.COLD, 1, True,
     [("client", "Stone & Son Suit Warehouse"), ("view", ViewType.COMMITMENT)]),
    (5, "ryan job interview elsewhere, keep it between us",
     "Ryan said he had a job interview elsewhere and asked me to keep it between us.",
     DataType.WARM, 5, True,
     [("team_member", "Ryan"), ("view", ViewType.TEAM_MEMBER_FILE)]),
    # Left proposed on purpose: live material for the validation UI demo.
    (2, "prince family asked about recycled paper options",
     "Prince Family Paper asked about recycled paper options.",
     DataType.COLD, 1, False,
     [("client", "Prince Family Paper")]),
    (1, "kelly unusually quiet today",
     "Kelly seemed unusually quiet today.",
     DataType.WARM, 2, False,
     [("team_member", "Kelly")]),
]

# Weekly mood per member, oldest week first (12 weeks). Ryan declines,
# Darryl goes silent after week 8 (None = no check-in that week).
F, C, P, PR, S, D = (MoodLevel.FLOW, MoodLevel.CTRL, MoodLevel.PRETZEL_DAY,
                     MoodLevel.PRESS, MoodLevel.STUCK, MoodLevel.DANGER)
MOOD_STORYLINES: dict[str, list[MoodLevel | None]] = {
    "Ryan":    [C, C, C, C, C, C, PR, PR, PR, PR, S, D],
    "Oscar":   [C, C, C, C, C, C, C, C, C, C, C, C],
    "Kelly":   [F, F, C, F, F, PR, F, F, F, C, F, F],
    "Phyllis": [C, F, C, F, C, F, C, F, C, F, C, F],
    "Stanley": [P, PR, P, PR, P, PR, P, PR, P, PR, P, PR],
    "Darryl":  [C, C, C, C, C, C, C, C, C, None, None, None],
}
WEEKS = 12


def seed(
    session_factory: sessionmaker[Session],
    llm: LLMProvider,
    vector_store: VectorStore,
) -> str:
    """Insert the demo dataset, embedding validated segments.

    Refuses to run on a non-empty roster: seeding is for fresh or reset
    databases, never a way to silently mix demo and real data.
    """
    with session_factory() as session:
        if session.query(TeamMember).count() > 0:
            return "Database already has team members: skipping (use --reset to start over)."

        members = {}
        for name, role in TEAM:
            profile = PROFILES.get(name, {})
            members[name] = TeamMember(
                full_name=name,
                role=role,
                birthday=(
                    datetime.strptime(profile["birthday"], "%Y-%m-%d").date()
                    if "birthday" in profile
                    else None
                ),
                personal_profile=profile.get("personal_profile"),
            )
        clients = {name: Client(name=name) for name in CLIENTS}
        session.add_all([*members.values(), *clients.values()])
        session.flush()

        projects = {}
        for name, client_name in PROJECTS:
            projects[name] = Project(
                name=name, client_id=clients[client_name].id if client_name else None
            )
        stakeholders = {
            name: Stakeholder(name=name, relationship_type=kind)
            for name, kind in STAKEHOLDERS
        }
        session.add_all([*projects.values(), *stakeholders.values()])
        session.flush()

        entity_ids = {
            "team_member": {name: m.id for name, m in members.items()},
            "client": {name: c.id for name, c in clients.items()},
            "project": {name: p.id for name, p in projects.items()},
            "stakeholder": {name: s.id for name, s in stakeholders.items()},
        }

        validated_segments = []
        for age, raw, content, data_type, sensitivity, validated, tags in SEGMENTS:
            entry = Entry(
                raw_content=raw,
                source_type=SourceType.NOTE,
                processing_status=ProcessingStatus.COMPLETE,
                created_at=days_ago(age),
            )
            session.add(entry)
            session.flush()
            segment = EntrySegment(
                entry_id=entry.id,
                content=content,
                segment_order=0,
                data_type=data_type,
                sensitivity_level=sensitivity,
                validation_status=(
                    ValidationStatus.VALIDATED if validated else ValidationStatus.PROPOSED
                ),
                created_at=days_ago(age),
            )
            session.add(segment)
            session.flush()
            for kind, target in tags:
                session.add(
                    SegmentTag(
                        segment_id=segment.id,
                        entity_type=EntityType(kind) if kind != "view" else EntityType.VIEW,
                        entity_id=entity_ids[kind][target] if kind != "view" else None,
                        view_type=target if kind == "view" else None,
                        proposed_by=ProposedBy.DWIGHT,
                        confidence=0.9,
                        validated=validated,
                        created_at=days_ago(age),
                    )
                )
            if validated:
                validated_segments.append(segment)

        for name, storyline in MOOD_STORYLINES.items():
            for week, mood in enumerate(storyline):
                if mood is None:
                    continue
                session.add(
                    MoodCheckin(
                        team_member_id=members[name].id,
                        mood_level=mood,
                        created_at=days_ago((WEEKS - week) * 7 - 3),
                    )
                )

        session.flush()
        # One batched embedding call for all validated segments, then one
        # upsert: the only non-deterministic (network) part of the seed.
        embeddings = llm.embed([segment.content for segment in validated_segments])
        vector_store.upsert(
            [
                SegmentVector(
                    segment_id=segment.id,
                    embedding=embedding,
                    metadata=flatten_segment_metadata(segment),
                )
                for segment, embedding in zip(validated_segments, embeddings)
            ]
        )
        session.commit()
        return (
            f"Seeded {len(TEAM)} members, {len(CLIENTS)} clients, "
            f"{len(SEGMENTS)} entries, {len(validated_segments)} segments embedded."
        )


def main() -> None:
    """CLI entry point: python -m backend.app.db.seed [--reset]."""
    parser = argparse.ArgumentParser(description="Seed the Dunder Mifflin demo dataset.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the SQLite file and the Chroma directory first.",
    )
    args = parser.parse_args()
    settings = get_settings()

    if args.reset:
        db_path = settings.database_url.removeprefix("sqlite:///")
        Path(db_path).unlink(missing_ok=True)
        shutil.rmtree(settings.chroma_dir, ignore_errors=True)
        print(f"Reset: removed {db_path} and {settings.chroma_dir}.")

    engine = build_engine(settings.database_url)
    init_db(engine)
    result = seed(
        build_session_factory(engine),
        build_llm(settings),
        ChromaStore(persist_dir=settings.chroma_dir),
    )
    print(result)


if __name__ == "__main__":
    main()
