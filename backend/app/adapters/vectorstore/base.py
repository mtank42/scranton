"""VectorStore: the semantic index seam.

The store receives already-computed embeddings and returns segment ids.
It never talks to a model (that is LLMProvider's job) and never stores
authoritative content (SQLite is the single source of truth for text).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentVector:
    """One embedded segment, ready for indexing.

    metadata carries what Ask Pam filters on: data_type, sensitivity_level
    and the flattened entity/view tags (SCRANTON_CONTEXT.md section 5).
    In the documentary collection (Darryl), segment_id carries the
    document CHUNK id: the contract is 'the id of the indexed unit'.
    """

    segment_id: int
    embedding: list[float]
    metadata: dict


@dataclass(frozen=True)
class Hit:
    """One retrieval result: the indexed unit's id and similarity score."""

    segment_id: int
    score: float
    metadata: dict


class VectorStore(ABC):
    """Abstract contract for indexing and querying segment vectors."""

    @abstractmethod
    def upsert(self, segments: list[SegmentVector]) -> None:
        """Index the given segments, replacing any previous version."""

    @abstractmethod
    def query(
        self, embedding: list[float], *, filters: dict | None = None, k: int = 8
    ) -> list[Hit]:
        """Return the k nearest segments, optionally filtered on metadata.

        Takes an embedding rather than a text: computing embeddings is the
        LLMProvider's responsibility, which keeps this store free of any
        model dependency. This deliberately refines the sketch signature.
        """

    @abstractmethod
    def delete(self, ids: list[int]) -> None:
        """Remove the given vectors from the index; unknown ids are a no-op.

        Needed by the corpus lifecycle (Darryl): a document gone from the
        shared folder must stop answering, so its chunk vectors leave the
        index the moment the sync notices. Segments never needed this -
        validation only ever adds.
        """
