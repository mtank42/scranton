"""ChromaStore: real local index roundtrips (no network, chroma is local)."""

import pytest

from backend.app.adapters.vectorstore.base import SegmentVector
from backend.app.adapters.vectorstore.chroma import ChromaStore


@pytest.fixture
def store(tmp_path) -> ChromaStore:
    """A ChromaStore on a throwaway directory."""
    return ChromaStore(persist_dir=str(tmp_path / "chroma"))


def seed(store: ChromaStore) -> None:
    """Index two orthogonal vectors with distinct metadata."""
    store.upsert(
        [
            SegmentVector(segment_id=1, embedding=[1.0, 0.0], metadata={"data_type": "cold"}),
            SegmentVector(
                segment_id=2,
                embedding=[0.0, 1.0],
                metadata={"data_type": "warm", "team_member_1": True},
            ),
        ]
    )


def test_chromadb_imports_on_this_python():
    """chromadb compatibility was a flagged risk: importing it is the check."""
    import chromadb  # noqa: F401


def test_construction_and_empty_upsert_touch_no_disk(tmp_path):
    """The client is lazy: no Chroma directory until a real call happens."""
    store = ChromaStore(persist_dir=str(tmp_path / "chroma"))
    store.upsert([])
    assert store._collection is None
    assert not (tmp_path / "chroma").exists()


def test_upsert_then_query_returns_nearest_first(store):
    """The closest vector comes back first, with a similarity score."""
    seed(store)
    hits = store.query([1.0, 0.1], k=2)
    assert [hit.segment_id for hit in hits] == [1, 2]
    assert hits[0].score > hits[1].score
    assert hits[0].metadata["data_type"] == "cold"


def test_query_filters_on_flattened_metadata(store):
    """A metadata filter restricts results even against a closer vector."""
    seed(store)
    hits = store.query([1.0, 0.1], filters={"data_type": "warm"}, k=2)
    assert [hit.segment_id for hit in hits] == [2]


def test_multi_key_filters_are_anded(store):
    """Several filter keys must all match (Chroma $and under the hood)."""
    seed(store)
    hits = store.query([0.0, 1.0], filters={"data_type": "warm", "team_member_1": True}, k=2)
    assert [hit.segment_id for hit in hits] == [2]
    assert store.query([0.0, 1.0], filters={"data_type": "cold", "team_member_1": True}, k=2) == []


def test_reupserting_a_segment_overwrites_not_duplicates(store):
    """Segment id doubles as Chroma id: re-validation must not duplicate."""
    seed(store)
    store.upsert(
        [SegmentVector(segment_id=1, embedding=[0.9, 0.1], metadata={"data_type": "warm"})]
    )
    hits = store.query([1.0, 0.0], k=8)
    assert len(hits) == 2
    updated = next(hit for hit in hits if hit.segment_id == 1)
    assert updated.metadata["data_type"] == "warm"