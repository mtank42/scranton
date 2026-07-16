"""Darryl the archivist: sync -> extract -> route -> version -> index.

The documentary counterpart of Tell Dwight, with the opposite gate: a
document placed in the folder shared with Scranton was validated BY
that human gesture (owner doctrine, day one), so nothing here is ever
'proposed'. Darryl detects, extracts, routes and versions - silently,
with no human decision to steal.

Design decisions (owner arbitrations, 2026-07-15):
- Routing is deterministic first (folder path and file name matched
  against the actual roster - no folder convention to configure, which
  is how one pipeline adapts to companies that all file differently),
  LLM second, and NEVER a bet: below the confidence floor the document
  goes to the unclassified bin - still queryable, feeding no file.
- Versions: file names normalized into a family_key; the most recent
  of a family answers by default (is_latest), all versions on demand.
- SQLite is the source of truth for text: chunks are re-read from it
  at answer time. The vector index only holds embeddings and scalar
  ids; a document gone from the source loses its vectors immediately.
"""

import hashlib
import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.adapters.documents.base import DocumentSource, SourceDocument
from backend.app.adapters.extraction.registry import is_catalog_only
from backend.app.adapters.llm.base import LLMProvider
from backend.app.adapters.vectorstore.base import SegmentVector, VectorStore
from backend.app.domain.models import (
    Client,
    Document,
    DocumentChunk,
    DocumentProposedBy,
    DocumentStatus,
    DocumentTag,
    EntityType,
    Project,
    utcnow,
)
from backend.app.domain.schemas import DarrylRouting, DarrylSyncReport, DocumentOut
from backend.app.services.llm_json import LLMContractError, complete_validated
from backend.app.services.prompts import build_darryl_messages


class DocumentNotFoundError(Exception):
    """The requested document id does not exist."""


class UnknownEntityError(Exception):
    """The classification target is not in the roster (closed world)."""


# Retrieval wants coherent slices: paragraphs are packed up to this
# size, never split. An oversized single paragraph stays whole.
CHUNK_TARGET_CHARS = 1200

# The source key of documents born INSIDE Scranton (edited documents,
# 2026-07-16). They have no connector behind them, so the sync
# reconciliation must never see them: a Drive pass would otherwise
# soft-delete every document the manager saved.
SCRANTON_SOURCE = "scranton"

# What the routing fallback gets to read: enough to recognize the
# subject, small enough to keep the call cheap.
ROUTING_EXCERPT_CHARS = 800

# Version markers stripped from a normalized title to form the family
# key: v3, def, final, copy counters... 4-digit numbers (years) are
# kept on purpose: 'bilan 2025' and 'bilan 2026' are different
# documents, not versions of one another.
VERSION_TOKENS = re.compile(
    r"\b(v\d+|version|def|vdef|vf|finale?|final|copie|copy|draft|brouillon|\d{1,2})\b"
)


def normalize_text(text: str) -> str:
    """Lowercase, accent-stripped, punctuation collapsed to single spaces.

    The comparison space where roster names meet folder paths and file
    names: 'Techni-Pneus' and 'techni_pneus' must be the same word.
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", stripped).strip()


def family_key_of(title: str) -> str:
    """The version family of a file name.

    'Rapport_SEO_final_V3_DEF(1).pdf' -> 'rapport seo'. Heuristic by
    design (owner arbitration): a missed exotic family means two
    versions answering instead of one - correctable, never blocking.
    """
    stem = title.rsplit(".", 1)[0] if "." in title else title
    normalized = normalize_text(stem)
    cleaned = re.sub(r"\s+", " ", VERSION_TOKENS.sub(" ", normalized)).strip()
    return cleaned or normalized or title.lower()


def chunk_text(text: str) -> list[str]:
    """Pack paragraphs into ~CHUNK_TARGET_CHARS retrieval slices."""
    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 1 > CHUNK_TARGET_CHARS:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks or [text.strip()]


def naive_utc(moment: datetime | None) -> datetime | None:
    """Timezone-aware -> naive UTC, the form SQLite stores and compares."""
    if moment is None or moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


class DarrylService:
    """Orchestrates the corpus pipeline. Pure logic: all I/O behind seams."""

    def __init__(
        self,
        source: DocumentSource,
        llm: LLMProvider,
        session_factory: sessionmaker[Session],
        vector_store: VectorStore,
        min_confidence: float = 0.75,
    ) -> None:
        """Wire the seams. vector_store is the DOCUMENTS collection (the
        second memory), never the segments one. min_confidence is the
        routing floor (settings.darryl_min_confidence): below it, the
        unclassified bin - Darryl never bets."""
        self.source = source
        self.llm = llm
        self.session_factory = session_factory
        self.vector_store = vector_store
        self.min_confidence = min_confidence

    # --- the sync: one full pass over the shared corpus ---

    def sync(self) -> DarrylSyncReport:
        """Diff the source against the corpus and reconcile.

        New document: ingest (extract, route, chunk, embed). Changed
        fingerprint: re-extract and re-index, keeping the routing.
        Gone from the source: soft delete and drop the vectors - the
        shared folder IS the consent, removing a file withdraws it.
        """
        source_docs = list(self.source.fetch())
        report = DarrylSyncReport(seen=len(source_docs))
        with self.session_factory() as session:
            existing = {
                document.origin_ref: document
                for document in session.scalars(
                    # Scranton-born documents are not the connector's to
                    # reconcile: absent from the source is their normal
                    # state, not a withdrawal of consent.
                    select(Document).where(Document.source != SCRANTON_SOURCE)
                )
            }
            seen_refs = set()
            for source_doc in source_docs:
                seen_refs.add(source_doc.origin_ref)
                current = existing.get(source_doc.origin_ref)
                if current is None:
                    self._ingest(session, source_doc)
                    report.added += 1
                elif (
                    current.deleted_at is not None
                    or current.content_sha256 != source_doc.content_sha256
                ):
                    self._refresh(session, current, source_doc)
                    report.updated += 1
                else:
                    # Same content, possibly moved or renamed: metadata
                    # follows silently (title, path, link, family).
                    self._refresh_metadata(current, source_doc)

            for origin_ref, document in existing.items():
                if origin_ref not in seen_refs and document.deleted_at is None:
                    document.deleted_at = utcnow()
                    self.vector_store.delete([chunk.id for chunk in document.chunks])
                    report.removed += 1

            self._recompute_families(session)
            report.unclassified = self._unclassified_count(session)
            session.commit()
        return report

    def _ingest(self, session: Session, source_doc: SourceDocument) -> None:
        """One new document: persist, route, chunk, embed."""
        document = Document(
            title=source_doc.title,
            mime_type=source_doc.mime_type,
            # The connector kind is the origin_ref prefix by convention.
            source=source_doc.origin_ref.split(":", 1)[0],
            origin_ref=source_doc.origin_ref,
            web_view_link=source_doc.web_view_link,
            folder_path=source_doc.folder_path,
            modified_at=naive_utc(source_doc.modified_at),
            content_sha256=source_doc.content_sha256,
            status=DocumentStatus.UNCLASSIFIED,
            family_key=family_key_of(source_doc.title),
        )
        session.add(document)
        session.flush()
        self._route(session, document, source_doc.text)
        self._index_chunks(session, document, source_doc.text)
        document.status = self._status_of(document, source_doc.text)

    def _refresh(
        self, session: Session, document: Document, source_doc: SourceDocument
    ) -> None:
        """Changed (or returned) content: replace the chunks, keep the routing.

        The routing survives on purpose: a v4 landing next to a v3 is
        the same deliverable for the same client, and a manager's manual
        filing must never be undone by an edit.
        """
        self._refresh_metadata(document, source_doc)
        document.content_sha256 = source_doc.content_sha256
        document.deleted_at = None
        self.vector_store.delete([chunk.id for chunk in document.chunks])
        document.chunks.clear()
        session.flush()
        self._index_chunks(session, document, source_doc.text)
        document.status = self._status_of(document, source_doc.text)

    @staticmethod
    def _refresh_metadata(document: Document, source_doc: SourceDocument) -> None:
        """Follow renames and moves: identity fields track the source."""
        document.title = source_doc.title
        document.folder_path = source_doc.folder_path
        document.web_view_link = source_doc.web_view_link
        document.modified_at = naive_utc(source_doc.modified_at)
        document.family_key = family_key_of(source_doc.title)

    def _status_of(self, document: Document, text: str | None) -> DocumentStatus:
        """Derive the filing status: bin, full index, or catalog entry."""
        if not document.tags:
            return DocumentStatus.UNCLASSIFIED
        return DocumentStatus.INDEXED if text else DocumentStatus.CATALOGED

    # --- routing: deterministic first, LLM second, never a bet ---

    def _route(self, session: Session, document: Document, text: str | None) -> None:
        """Attach client/project tags, or none (the unclassified bin).

        The deterministic pass matches the ACTUAL roster against folder
        path and file name: no filing convention to configure, so any
        company whose names appear somewhere in their tree routes for
        free. Only when that finds nothing does the LLM read an excerpt,
        closed-world, under the confidence floor rule.
        """
        roster = self._roster(session)
        signal_text = normalize_text(f"{document.folder_path} {document.title}")
        matched = [
            (entity_type, entity_id)
            for entity_type, entity_id, name in roster
            # Names shorter than 3 characters would match everywhere.
            if len(name) >= 3 and name in signal_text
        ]
        if matched:
            for entity_type, entity_id in matched:
                session.add(
                    DocumentTag(
                        document_id=document.id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        proposed_by=DocumentProposedBy.DARRYL,
                        confidence=1.0,
                    )
                )
            session.flush()
            return

        proposal = self._llm_routing(session, document, text)
        known = {(entity_type, entity_id) for entity_type, entity_id, _ in roster}
        for tag in proposal.tags:
            # Closed world + the floor: an unknown id or a hesitant
            # score both mean the bin, never a plausible filing.
            if (tag.entity_type, tag.entity_id) not in known:
                continue
            if tag.confidence < self.min_confidence:
                continue
            session.add(
                DocumentTag(
                    document_id=document.id,
                    entity_type=tag.entity_type,
                    entity_id=tag.entity_id,
                    proposed_by=DocumentProposedBy.DARRYL,
                    confidence=tag.confidence,
                )
            )
        session.flush()

    def _llm_routing(
        self, session: Session, document: Document, text: str | None
    ) -> DarrylRouting:
        """Ask the model for a second opinion; failures mean the bin."""
        roster_lines = ["clients: " + self._format_entities(session, Client)]
        roster_lines.append("projects: " + self._format_entities(session, Project))
        try:
            return complete_validated(
                self.llm,
                build_darryl_messages(
                    document.title,
                    document.folder_path,
                    (text or "")[:ROUTING_EXCERPT_CHARS],
                    "\n".join(roster_lines),
                ),
                DarrylRouting,
            )
        except LLMContractError:
            # A model hiccup must never fail a sync: the document lands
            # in the bin, where the manager can file it.
            return DarrylRouting()

    @staticmethod
    def _format_entities(session: Session, model: type) -> str:
        """Render roster rows as 'id=N name' pairs, or an explicit 'none'."""
        rows = session.scalars(select(model)).all()
        if not rows:
            return "(none)"
        return "; ".join(f"id={row.id} {row.name}" for row in rows)

    @staticmethod
    def _roster(session: Session) -> list[tuple[EntityType, int, str]]:
        """(type, id, normalized name) for every client and project."""
        roster: list[tuple[EntityType, int, str]] = []
        for entity_type, model in ((EntityType.CLIENT, Client), (EntityType.PROJECT, Project)):
            for row in session.scalars(select(model)):
                roster.append((entity_type, row.id, normalize_text(row.name or "")))
        return roster

    # --- indexing: SQLite holds the text, Chroma the vectors ---

    def _index_chunks(self, session: Session, document: Document, text: str | None) -> None:
        """Persist the chunks and embed them into the documents collection.

        A content-less document (spreadsheets, failed extraction) gets
        ONE catalog chunk - its name, folder and date as text - so 'the
        Techni-Pneus tracking file' is still findable by meaning.
        """
        if text and text.strip():
            contents = chunk_text(text)
        else:
            modified = (
                f", modified {document.modified_at:%Y-%m-%d}" if document.modified_at else ""
            )
            contents = [
                f"Cataloged file: {document.title} "
                f"(folder: {document.folder_path or 'shared root'}{modified})"
            ]
        chunks = [
            DocumentChunk(document_id=document.id, chunk_order=order, content=content)
            for order, content in enumerate(contents)
        ]
        session.add_all(chunks)
        session.flush()
        embeddings = self.llm.embed([chunk.content for chunk in chunks])
        self.vector_store.upsert(
            [
                SegmentVector(
                    segment_id=chunk.id,
                    embedding=embedding,
                    # Scalars only (Chroma rule). Routing, versions and
                    # deletion live in SQLite and are applied at re-read
                    # time: static metadata means no re-embedding when a
                    # document is re-filed or a newer version lands.
                    metadata={
                        "chunk_id": chunk.id,
                        "document_id": document.id,
                        "data_type": "cold",
                    },
                )
                for chunk, embedding in zip(chunks, embeddings)
            ]
        )

    # --- Scranton-born documents (edited documents, 2026-07-16) ---

    def file_generated_document(
        self,
        title: str,
        text: str,
        origin_ref: str,
        entity_type: EntityType,
        entity_id: int,
    ) -> None:
        """File one edited document into the corpus, or refresh it.

        The save gesture IS the filing (same doctrine as the shared
        folder), so the routing is a manager tag at confidence 1.0 -
        no Darryl guesswork. Client/project targets only: the caller
        (the editing engine) enforces that person-targeted documents
        never reach the corpus.
        """
        sha = hashlib.sha256(text.encode()).hexdigest()
        with self.session_factory() as session:
            document = session.scalars(
                select(Document).where(Document.origin_ref == origin_ref)
            ).first()
            if document is None:
                document = Document(
                    title=title,
                    mime_type="text/markdown",
                    source=SCRANTON_SOURCE,
                    origin_ref=origin_ref,
                    content_sha256=sha,
                    status=DocumentStatus.INDEXED,
                    family_key=family_key_of(title),
                )
                session.add(document)
                session.flush()
                session.add(
                    DocumentTag(
                        document_id=document.id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        proposed_by=DocumentProposedBy.MANAGER,
                        confidence=1.0,
                    )
                )
                session.flush()
                self._index_chunks(session, document, text)
            elif document.content_sha256 != sha or document.title != title:
                document.title = title
                document.family_key = family_key_of(title)
                document.content_sha256 = sha
                document.modified_at = utcnow()
                self.vector_store.delete([chunk.id for chunk in document.chunks])
                document.chunks.clear()
                session.flush()
                self._index_chunks(session, document, text)
            session.commit()

    # --- versions: one family, one default voice ---

    @staticmethod
    def _recompute_families(session: Session) -> None:
        """Flag the most recent living member of each family as is_latest."""
        documents = session.scalars(
            select(Document).where(Document.deleted_at.is_(None))
        ).all()
        families: dict[str, list[Document]] = {}
        for document in documents:
            families.setdefault(document.family_key, []).append(document)
        for members in families.values():
            # modified_at can be missing (source without dates): fall
            # back to ingestion time, then id, for a stable order.
            # naive_utc on both: rows read from SQLite carry naive
            # datetimes while freshly flushed defaults are aware, and
            # Python refuses to compare the two.
            latest = max(
                members,
                key=lambda doc: (
                    naive_utc(doc.modified_at or doc.ingested_at),
                    naive_utc(doc.ingested_at),
                    doc.id,
                ),
            )
            for document in members:
                document.is_latest = document is latest

    @staticmethod
    def _unclassified_count(session: Session) -> int:
        """Current size of the bin (living documents only)."""
        return len(
            session.scalars(
                select(Document.id).where(
                    Document.status == DocumentStatus.UNCLASSIFIED,
                    Document.deleted_at.is_(None),
                )
            ).all()
        )

    # --- the manager's corrections and the audit surface ---

    def classify(
        self, document_id: int, entity_type: EntityType, entity_id: int
    ) -> DocumentOut:
        """File one document under a client or project: a manager decision.

        Replaces the existing routing (a decision, not a suggestion) and
        pulls the document out of the bin. Closed world applies to the
        manager too: the target must exist in the roster.
        """
        with self.session_factory() as session:
            document = session.get(Document, document_id)
            if document is None or document.deleted_at is not None:
                raise DocumentNotFoundError(f"No document with id {document_id}.")
            model = Client if entity_type == EntityType.CLIENT else Project
            if session.get(model, entity_id) is None:
                raise UnknownEntityError(
                    f"No {entity_type.value} with id {entity_id} in the roster."
                )
            # Through the relationship (not session.add): the factory
            # runs expire_on_commit=False, so the in-memory collection
            # is what the response below will serialize.
            document.tags.clear()
            document.tags.append(
                DocumentTag(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    proposed_by=DocumentProposedBy.MANAGER,
                    confidence=1.0,
                )
            )
            document.status = (
                DocumentStatus.CATALOGED
                if is_catalog_only(document.mime_type)
                else DocumentStatus.INDEXED
            )
            session.commit()
            return DocumentOut.model_validate(document)

    def recent(self, limit: int = 5, offset: int = 0) -> list[DocumentOut]:
        """The last ingested living documents: the Pam overlay strip."""
        with self.session_factory() as session:
            documents = session.scalars(
                select(Document)
                .where(Document.deleted_at.is_(None))
                .order_by(Document.ingested_at.desc(), Document.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            return [DocumentOut.model_validate(document) for document in documents]

    def unclassified(self) -> list[DocumentOut]:
        """The bin, newest first: what the manager may want to file."""
        with self.session_factory() as session:
            documents = session.scalars(
                select(Document)
                .where(
                    Document.status == DocumentStatus.UNCLASSIFIED,
                    Document.deleted_at.is_(None),
                )
                .order_by(Document.ingested_at.desc(), Document.id.desc())
            ).all()
            return [DocumentOut.model_validate(document) for document in documents]
