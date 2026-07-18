"""Demo dataset: the fictitious Dunder Mifflin team, ~3 months of history.

Deterministic on purpose: segments are pre-written (no LLM call decides
the data), so the demo is reproducible and the golden queries have known
right answers. The only real model calls are the embeddings of validated
segments, made once at seed time.

The storylines are demo material:
- Ryan's mood declines over the quarter (ctrl -> press -> stuck ->
  danger) with two sensitive warm segments: the act-at-week-6 story.
- Val stops checking in: the silence signal.
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
    BIRTHDAY_YEAR,
    Client,
    DataType,
    Document,
    DocumentChunk,
    DocumentProposedBy,
    DocumentStatus,
    DocumentTag,
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
    User,
    UserRole,
    ValidationStatus,
    ViewType,
)
from backend.app.services.auth_service import hash_password
from backend.app.services.dwight_service import flatten_segment_metadata


def days_ago(days: int) -> datetime:
    """Naive-UTC timestamp 'days' in the past (how SQLite stores our dates)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)


# --- The dataset (names reserved for fictitious users, SCRANTON_CONTEXT §3) ---

# Demo credentials (printed by the seed so a demo is one command away;
# real deployments create their accounts through the first-run setup).
MANAGER_EMAIL = "michael@dundermifflin.com"
MANAGER_PASSWORD = "worldsbestboss"
MEMBER_PASSWORD = "pretzelday"

TEAM = [
    ("Ryan", "Junior salesman"),
    ("Oscar", "Accountant"),
    ("Kelly", "Customer service"),
    ("Phyllis", "Saleswoman"),
    ("Stanley", "Salesman"),
    ("Val", "Warehouse foreman"),
]

# Member-owned data (human profile). Sparse on purpose: profiles grow
# from real conversations, they are not an HR form to fill. Birthdays
# are day + month only (year fixed to 2000, never shown - owner rule)
# and RELATIVE to seed day, like the rest of the dataset: Kelly is
# Maire de Scranton on demo day, Val's reminder shows at J-3.
PROFILES: dict[str, dict] = {
    "Kelly": {
        "birthday_in_days": 0,
        "personal_profile": "Loves romantic comedies and celebrity news. Collects lip gloss.",
    },
    "Val": {
        "birthday_in_days": 3,
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
    # Cold activity for Ryan (QA 2026-07-14: annual review and briefs had
    # nothing operational to chew on) and validated cold matter for the
    # Prince Family Paper client template.
    (55, "ryan closed first solo deal, lackawanna 30 extra boxes",
     "Ryan closed his first solo deal: a 30-box add-on with Lackawanna County Schools.",
     DataType.COLD, 1, True,
     [("team_member", "Ryan"), ("client", "Lackawanna County Schools"), ("view", ViewType.ANNUAL_REVIEW)]),
    (50, "keystone late twice this month, flagged to account manager",
     "Keystone Logistics was late on two deliveries this month; flagged to their account manager.",
     DataType.COLD, 2, True,
     [("stakeholder", "Keystone Logistics")]),
    # Ryan and Kelly on the same client: the two-member Pam answer
    # ("what do they share?") has a real overlap to report.
    (45, "ryan and kelly ran prince family follow up call, recovery plan accepted",
     "Ryan and Kelly ran the Prince Family Paper follow-up call together; the recovery plan was accepted.",
     DataType.COLD, 1, True,
     [("team_member", "Ryan"), ("team_member", "Kelly"), ("client", "Prince Family Paper")]),
    (40, "routes overhaul kickoff val owns schedule draft in 2 weeks",
     "Delivery routes overhaul kickoff: Val owns the new schedule, first draft expected in two weeks.",
     DataType.COLD, 1, True,
     [("team_member", "Val"), ("project", "Delivery routes overhaul"), ("view", ViewType.PROJECT_FILE)]),
    (35, "phyllis mentored ryan on cold calls, keep it quiet",
     "Phyllis quietly mentored Ryan on cold calls this week; she did not want it mentioned in the meeting.",
     DataType.WARM, 3, True,
     [("team_member", "Phyllis"), ("team_member", "Ryan")]),
    (30, "oscar found recurring invoicing error on lackawanna",
     "Oscar flagged a recurring invoicing error on the Lackawanna account; fix agreed with accounting.",
     DataType.COLD, 2, True,
     [("team_member", "Oscar"), ("client", "Lackawanna County Schools")]),
    (25, "ryan owns the weekly q3 cardstock reporting, first report on time",
     "Ryan took over the weekly reporting on the Q3 cardstock contract; first report delivered on time.",
     DataType.COLD, 1, True,
     [("team_member", "Ryan"), ("project", "Q3 cardstock contract"), ("view", ViewType.PROJECT_FILE)]),
    (20, "ryan exhausted, wonders if sales is right for him",
     "Ryan mentioned he is exhausted and wonders if sales is the right fit for him.",
     DataType.WARM, 4, True,
     [("team_member", "Ryan"), ("view", ViewType.TEAM_MEMBER_FILE)]),
    (15, "promised stone and son revised quote before end of month",
     "Promised Stone & Son a revised quote before the end of the month.",
     DataType.COLD, 1, True,
     [("client", "Stone & Son Suit Warehouse"), ("view", ViewType.COMMITMENT)]),
    (10, "prince family signed the recycled paper trial, 20 boxes monthly",
     "Prince Family Paper signed the recycled paper trial: 20 boxes monthly starting next month.",
     DataType.COLD, 1, True,
     [("client", "Prince Family Paper"), ("view", ViewType.COMMITMENT)]),
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
# Val goes silent after week 8 (None = no check-in that week).
F, C, P, PR, S, D = (MoodLevel.FLOW, MoodLevel.CTRL, MoodLevel.PRETZEL_DAY,
                     MoodLevel.PRESS, MoodLevel.STUCK, MoodLevel.DANGER)
MOOD_STORYLINES: dict[str, list[MoodLevel | None]] = {
    "Ryan":    [C, C, C, C, C, C, PR, PR, PR, PR, S, D],
    "Oscar":   [C, C, C, C, C, C, C, C, C, C, C, C],
    "Kelly":   [F, F, C, F, F, PR, F, F, F, C, F, F],
    "Phyllis": [C, F, C, F, C, F, C, F, C, F, C, F],
    "Stanley": [P, PR, P, PR, P, PR, P, PR, P, PR, P, PR],
    "Val":     [C, C, C, C, C, C, C, C, C, None, None, None],
}
WEEKS = 12

# Darryl's demo corpus (2026-07-15, enriched 2026-07-17 - the owner
# called four documents 'rabougri'): two version families (only the
# latest answers by default), two cataloged spreadsheets, two bin
# items, every client and one project covered. One entry per document:
# (days_ago, title, mime, folder, status, is_latest, family,
# (entity_kind, entity_name) or None, chunk_text).
# QA anchors - the v6 checklist cites these titles, NEVER rename them:
# Contrat_papier_recycle_V2_DEF.md, Suivi_Lackawanna_County_Schools.xlsx,
# notes_entrepot_vrac.md.
MD = "text/markdown"
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCUMENTS = [
    (60, "Contrat_papier_recycle_V1.md", MD, "Clients/Prince Family Paper",
     DocumentStatus.INDEXED, False, "contrat papier recycle",
     ("client", "Prince Family Paper"),
     "Recycled paper trial, draft terms: 15 boxes monthly, pricing to be "
     "confirmed with accounting before signature."),
    (9, "Contrat_papier_recycle_V2_DEF.md", MD, "Clients/Prince Family Paper",
     DocumentStatus.INDEXED, True, "contrat papier recycle",
     ("client", "Prince Family Paper"),
     "Recycled paper trial, signed: 20 boxes monthly starting next month, "
     "delivery on the first Tuesday of each month, renewal reviewed after "
     "one quarter."),
    (7, "CR_appel_Prince_premiere_livraison.md", MD,
     "Clients/Prince Family Paper",
     DocumentStatus.INDEXED, True, "cr appel prince premiere livraison",
     ("client", "Prince Family Paper"),
     "Call notes with Prince Family Paper: first recycled paper delivery "
     "confirmed for the first Tuesday, contact praised our responsiveness "
     "and asked whether a bulk discount applies from 30 boxes monthly."),
    (14, "Suivi_Lackawanna_County_Schools.xlsx", XLSX, "Clients",
     DocumentStatus.CATALOGED, True, "suivi lackawanna county schools",
     ("client", "Lackawanna County Schools"),
     "Cataloged file: Suivi_Lackawanna_County_Schools.xlsx (folder: Clients)"),
    (40, "CR_reunion_Lackawanna_rentree.docx", DOCX,
     "Clients/Lackawanna County Schools",
     DocumentStatus.INDEXED, True, "cr reunion lackawanna rentree",
     ("client", "Lackawanna County Schools"),
     "Back-to-school planning meeting with Lackawanna County Schools: "
     "cardstock volumes confirmed for Q3, deliveries only on Tuesday "
     "mornings during term, the procurement office prefers email over "
     "phone for every follow-up."),
    (45, "Devis_Stone_and_Son_letterhead.pdf", PDF,
     "Clients/Stone & Son Suit Warehouse",
     DocumentStatus.INDEXED, True, "devis stone and son letterhead",
     ("client", "Stone & Son Suit Warehouse"),
     "Quote for Stone & Son Suit Warehouse: 5000 letterhead sheets on "
     "90g ivory stock, three pricing tiers by volume, embossed logo "
     "option quoted separately, offer valid 30 days."),
    (26, "Grille_tarifs_Prince_2026.xlsx", XLSX, "Clients/Prince Family Paper",
     DocumentStatus.CATALOGED, True, "grille tarifs prince 2026",
     ("client", "Prince Family Paper"),
     "Cataloged file: Grille_tarifs_Prince_2026.xlsx "
     "(folder: Clients/Prince Family Paper)"),
    (35, "Plan_tournees_livraison_draft.md", MD, "Projets/Delivery routes",
     DocumentStatus.INDEXED, False, "plan tournees livraison",
     ("project", "Delivery routes overhaul"),
     "Delivery routes overhaul, first draft: three routes around the "
     "business park, morning slots only, the south loop looks overloaded."),
    (18, "Plan_tournees_livraison_V2.md", MD, "Projets/Delivery routes",
     DocumentStatus.INDEXED, True, "plan tournees livraison",
     ("project", "Delivery routes overhaul"),
     "Delivery routes overhaul, revised plan: four routes, Keystone "
     "Logistics takes the north loop as subcontractor, fuel costs "
     "reviewed monthly, go-live after the Q3 rush."),
    (12, "Brief_rentree_Lackawanna.docx", DOCX,
     "Clients/Lackawanna County Schools",
     DocumentStatus.INDEXED, True, "brief rentree lackawanna",
     ("client", "Lackawanna County Schools"),
     "Sales brief for the school season: Lackawanna volumes up, cardstock "
     "is the growth line, watch the invoicing error flagged by accounting "
     "and confirm the fix before the next billing cycle."),
    (3, "notes_entrepot_vrac.md", MD, "Divers",
     DocumentStatus.UNCLASSIFIED, True, "notes entrepot vrac", None,
     "Warehouse loose notes: pallet turnaround ideas, forklift maintenance "
     "calendar, and the mezzanine storage question to settle."),
    (2, "Menu_traiteur_pretzel_day.md", MD, "Divers",
     DocumentStatus.UNCLASSIFIED, True, "menu traiteur pretzel day", None,
     "Caterer menu options for the next office pretzel day: classic "
     "salted, cinnamon sugar, and a savory cheese tray, quote per head "
     "with delivery before noon."),
]


def seed(
    session_factory: sessionmaker[Session],
    llm: LLMProvider,
    vector_store: VectorStore,
    doc_vector_store: VectorStore | None = None,
) -> str:
    """Insert the demo dataset, embedding validated segments.

    Refuses to run on a non-empty roster: seeding is for fresh or reset
    databases, never a way to silently mix demo and real data.
    doc_vector_store receives the demo corpus vectors (the 'documents'
    collection); None skips the corpus embedding, which keeps older
    callers valid.
    """
    with session_factory() as session:
        if session.query(TeamMember).count() > 0:
            return "Database already has team members: skipping (use --reset to start over)."

        members = {}
        for name, role in TEAM:
            profile = PROFILES.get(name, {})
            birthday = None
            if "birthday_in_days" in profile:
                occurrence = (
                    datetime.now(timezone.utc) + timedelta(days=profile["birthday_in_days"])
                ).date()
                birthday = occurrence.replace(year=BIRTHDAY_YEAR)
            members[name] = TeamMember(
                full_name=name,
                role=role,
                birthday=birthday,
                personal_profile=profile.get("personal_profile"),
            )
        clients = {name: Client(name=name) for name in CLIENTS}
        session.add_all([*members.values(), *clients.values()])
        session.flush()

        # Login accounts (identity session, 2026-07-18): the demo manager
        # and one account per roster member. Passwords are hashed once per
        # distinct value and reused (argon2 is slow on purpose; six
        # identical demo passwords do not need six hashes). Demo accounts
        # skip the forced first-login change: a demo must open, not nag.
        manager_hash = hash_password(MANAGER_PASSWORD)
        member_hash = hash_password(MEMBER_PASSWORD)
        session.add(
            User(
                email=MANAGER_EMAIL,
                password_hash=manager_hash,
                role=UserRole.MANAGER,
                full_name="Michael Scott",
                # Eligible Maire de Scranton (owner decision 2026-07-14);
                # J-6 puts him in the upcoming-birthdays reminder window.
                birthday=(datetime.now(timezone.utc) + timedelta(days=6))
                .date()
                .replace(year=BIRTHDAY_YEAR),
            )
        )
        session.add_all(
            [
                User(
                    email=f"{name.lower()}@dundermifflin.com",
                    password_hash=member_hash,
                    role=UserRole.MEMBER,
                    team_member_id=member.id,
                )
                for name, member in members.items()
            ]
        )

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

        # Darryl's demo corpus: documents pre-filed as a real sync would
        # leave them (routing tags at 1.0, one bin item, one catalog
        # entry, the version family with only the DEF as latest).
        chunks: list[DocumentChunk] = []
        for age, title, mime, folder, doc_status, latest, family, entity, text in DOCUMENTS:
            document = Document(
                title=title,
                mime_type=mime,
                source="seed",
                origin_ref=f"seed:{title}",
                web_view_link=None,
                folder_path=folder,
                modified_at=days_ago(age),
                content_sha256=f"seed-{title}",
                status=doc_status,
                family_key=family,
                is_latest=latest,
                ingested_at=days_ago(age),
            )
            session.add(document)
            session.flush()
            if entity:
                # Routed as a real sync would have: client or project,
                # resolved by name against the roster planted above.
                kind, name = entity
                target = clients[name] if kind == "client" else projects[name]
                session.add(
                    DocumentTag(
                        document_id=document.id,
                        entity_type=EntityType.CLIENT if kind == "client" else EntityType.PROJECT,
                        entity_id=target.id,
                        proposed_by=DocumentProposedBy.DARRYL,
                        confidence=1.0,
                    )
                )
            chunk = DocumentChunk(document_id=document.id, chunk_order=0, content=text)
            session.add(chunk)
            session.flush()
            chunks.append(chunk)

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
        if doc_vector_store is not None:
            chunk_embeddings = llm.embed([chunk.content for chunk in chunks])
            doc_vector_store.upsert(
                [
                    SegmentVector(
                        segment_id=chunk.id,
                        embedding=embedding,
                        metadata={
                            "chunk_id": chunk.id,
                            "document_id": chunk.document_id,
                            "data_type": "cold",
                        },
                    )
                    for chunk, embedding in zip(chunks, chunk_embeddings)
                ]
            )
        session.commit()
        return (
            f"Seeded {len(TEAM)} members, {len(CLIENTS)} clients, "
            f"{len(SEGMENTS)} entries, {len(validated_segments)} segments embedded, "
            f"{len(DOCUMENTS)} corpus documents.\n"
            f"Demo accounts: {MANAGER_EMAIL} / {MANAGER_PASSWORD} (manager), "
            f"<firstname>@dundermifflin.com / {MEMBER_PASSWORD} (members)."
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
        doc_vector_store=ChromaStore(
            persist_dir=settings.chroma_dir, collection_name="documents"
        ),
    )
    print(result)


if __name__ == "__main__":
    main()
