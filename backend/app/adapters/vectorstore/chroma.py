"""ChromaDB implementation of VectorStore.

Indexing (upsert) is live since M1: validated segments are embedded and
stored here. Retrieval (query) lands in M2 with Ask Pam.
"""

import chromadb

from backend.app.adapters.vectorstore.base import Hit, SegmentVector, VectorStore


class ChromaStore(VectorStore):
    """Local persistent Chroma index: one collection, one vector per segment."""

    COLLECTION_NAME = "segments"

    def __init__(self, persist_dir: str) -> None:
        """Store the target directory: the client itself is created lazily.

        persist_dir comes from settings (CHROMA_DIR): data location is
        configuration, never code. Lazy creation keeps app startup and
        offline tests fast: no disk activity until the first upsert.
        """
        self.persist_dir = persist_dir
        self._collection: chromadb.Collection | None = None

    def _get_collection(self) -> chromadb.Collection:
        """Create (or open) the persistent collection on first use."""
        if self._collection is None:
            client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = client.get_or_create_collection(self.COLLECTION_NAME)
        return self._collection

    def upsert(self, segments: list[SegmentVector]) -> None:
        """Index the given segments, replacing any previous version.

        The segment id doubles as the Chroma document id, so re-validating
        a segment overwrites its vector instead of duplicating it. Only
        vectors and metadata are stored: SQLite remains the single source
        of truth for the text itself.
        """
        if not segments:
            return
        self._get_collection().upsert(
            ids=[str(segment.segment_id) for segment in segments],
            embeddings=[segment.embedding for segment in segments],
            metadatas=[segment.metadata for segment in segments],
        )

    def query(
        self, embedding: list[float], *, filters: dict | None = None, k: int = 8
    ) -> list[Hit]:
        """Not implemented yet: M2 (Ask Pam) brings retrieval."""
        raise NotImplementedError("ChromaStore.query lands in M2 (Ask Pam).")
