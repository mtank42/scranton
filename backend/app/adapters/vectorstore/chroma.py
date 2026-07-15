"""ChromaDB implementation of VectorStore.

Indexing (upsert) is live since M1, retrieval (query) since M2. The
store only ever sees embeddings and metadata: SQLite remains the single
source of truth for segment text.
"""

import chromadb

from backend.app.adapters.vectorstore.base import Hit, SegmentVector, VectorStore


class ChromaStore(VectorStore):
    """Local persistent Chroma index: one collection, one vector per unit."""

    def __init__(self, persist_dir: str, collection_name: str = "segments") -> None:
        """Store the target directory: the client itself is created lazily.

        persist_dir comes from settings (CHROMA_DIR): data location is
        configuration, never code. Lazy creation keeps app startup and
        offline tests fast: no disk activity until the first real call.
        collection_name separates the two memories (owner arbitration,
        2026-07-15): 'segments' for the human layer, 'documents' for
        Darryl's corpus - different lifecycles, one query interface.
        """
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._collection: chromadb.Collection | None = None

    def _get_collection(self) -> chromadb.Collection:
        """Create (or open) the persistent collection on first use.

        Cosine space (not the default L2) because embedding similarity is
        directional: two segments about the same topic should match even
        if their vector magnitudes differ.
        """
        if self._collection is None:
            client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = client.get_or_create_collection(
                self.collection_name, metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def upsert(self, segments: list[SegmentVector]) -> None:
        """Index the given segments, replacing any previous version.

        The segment id doubles as the Chroma document id, so re-validating
        a segment overwrites its vector instead of duplicating it.
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
        """Return the k nearest segments, best match first.

        score is a similarity: 1.0 - cosine distance, so 1.0 means
        identical direction and values fall from there. filters maps
        flattened metadata keys to expected values (e.g.
        {'team_member_3': True} or {'data_type': 'warm'}).
        """
        results = self._get_collection().query(
            query_embeddings=[embedding],
            n_results=k,
            where=self._to_where(filters),
            include=["metadatas", "distances"],
        )
        return [
            Hit(segment_id=int(hit_id), score=1.0 - distance, metadata=metadata)
            for hit_id, distance, metadata in zip(
                results["ids"][0], results["distances"][0], results["metadatas"][0]
            )
        ]

    def delete(self, ids: list[int]) -> None:
        """Drop the given vectors; Chroma ignores ids it does not hold."""
        if not ids:
            return
        self._get_collection().delete(ids=[str(unit_id) for unit_id in ids])

    @staticmethod
    def _to_where(filters: dict | None) -> dict | None:
        """Translate a flat filters dict into Chroma's where syntax.

        Chroma accepts {key: value} for a single condition but requires an
        explicit $and wrapper for several: hiding that quirk here keeps the
        VectorStore contract a plain dict.
        """
        if not filters:
            return None
        if len(filters) == 1:
            return dict(filters)
        return {"$and": [{key: value} for key, value in filters.items()]}
