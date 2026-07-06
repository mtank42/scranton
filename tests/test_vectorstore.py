"""ChromaStore: import compatibility, laziness, and the M2 boundary."""

import pytest

from backend.app.adapters.vectorstore.chroma import ChromaStore


def test_chromadb_imports_on_this_python():
    """chromadb compatibility was a flagged risk: importing it is the check."""
    import chromadb  # noqa: F401


def test_construction_and_empty_upsert_touch_no_disk(tmp_path):
    """The client is lazy: no Chroma directory until a real upsert happens."""
    store = ChromaStore(persist_dir=str(tmp_path / "chroma"))
    store.upsert([])
    assert store._collection is None
    assert not (tmp_path / "chroma").exists()


def test_query_is_deferred_to_m2(tmp_path):
    """Retrieval lands with Ask Pam: until then it must fail loudly."""
    store = ChromaStore(persist_dir=str(tmp_path))
    with pytest.raises(NotImplementedError):
        store.query([0.1, 0.2], k=3)
