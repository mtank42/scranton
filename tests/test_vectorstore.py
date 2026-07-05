"""ChromaStore stub: import compatibility and explicit not-implemented state."""

import pytest

from backend.app.adapters.vectorstore.chroma import ChromaStore


def test_chromadb_imports_on_this_python():
    """chromadb compatibility was a flagged risk: importing it is the check."""
    import chromadb  # noqa: F401


def test_store_holds_config_but_defers_indexing(tmp_path):
    """The seam exists now; the real index lands in M2 (Ask Pam)."""
    store = ChromaStore(persist_dir=str(tmp_path))
    assert store.persist_dir == str(tmp_path)
    with pytest.raises(NotImplementedError):
        store.upsert([])
