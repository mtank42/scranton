"""ChromaDB implementation of VectorStore: stub until M2 (Ask Pam).

The top-level import below is intentional even though the methods are
not implemented yet: it proves at test time that chromadb installs and
imports cleanly on this Python version, a compatibility risk flagged in
PRODUCT_ROADMAP.md section 8.
"""

import chromadb  # noqa: F401  (compatibility check now, real use in M2)

from backend.app.adapters.vectorstore.base import Hit, SegmentVector, VectorStore


class ChromaStore(VectorStore):
    """Local persistent Chroma index: one collection, one vector per segment."""

    COLLECTION_NAME = "segments"

    def __init__(self, persist_dir: str) -> None:
        """Store the target directory: the client itself is created in M2.

        persist_dir comes from settings (CHROMA_DIR): data location is
        configuration, never code, so the index can live on a local disk,
        a NAS mount, or a cloud volume.
        """
        self.persist_dir = persist_dir

    def upsert(self, segments: list[SegmentVector]) -> None:
        """Not implemented yet: M2 (Ask Pam) brings the real index."""
        raise NotImplementedError("ChromaStore.upsert lands in M2 (Ask Pam).")

    def query(
        self, embedding: list[float], *, filters: dict | None = None, k: int = 8
    ) -> list[Hit]:
        """Not implemented yet: M2 (Ask Pam) brings retrieval."""
        raise NotImplementedError("ChromaStore.query lands in M2 (Ask Pam).")
