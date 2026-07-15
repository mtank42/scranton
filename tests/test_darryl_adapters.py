"""Darryl's edges: the extraction registry, the local source, the API.

The docx and pptx round-trips use the real libraries (they can write as
well as read, so no fixture files to maintain); everything stays on
disk and offline.
"""

import io

from backend.app.adapters.documents.base import DocumentSource, SourceDocument
from backend.app.adapters.documents.local import LocalDocumentSource
from backend.app.adapters.extraction.registry import (
    DOCX_MIME,
    PPTX_MIME,
    extract_content,
    is_catalog_only,
    is_supported,
)
from backend.app.api.deps import get_darryl_service
from backend.app.services.darryl_service import DarrylService
from tests.conftest import FakeVectorStore, ScriptedLLMProvider
from tests.test_darryl_service import FakeDocumentSource, source_doc

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --- extraction registry ---


def docx_bytes(text: str) -> bytes:
    from docx import Document

    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph(text)
    document.save(buffer)
    return buffer.getvalue()


def test_docx_round_trip():
    """Word in, plain text out."""
    assert "quarterly report" in extract_content(DOCX_MIME, docx_bytes("The quarterly report."))


def test_pptx_round_trip():
    """Slides in, their text frames out."""
    from pptx import Presentation
    from pptx.util import Inches

    buffer = io.BytesIO()
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    box.text_frame.text = "Roadmap slide"
    presentation.save(buffer)
    assert "Roadmap slide" in extract_content(PPTX_MIME, buffer.getvalue())


def test_spreadsheets_are_catalog_only_and_corrupt_files_never_raise():
    """The owner's xlsx rule, and extraction failures returning None."""
    assert is_catalog_only(XLSX_MIME) and is_supported(XLSX_MIME)
    assert extract_content(XLSX_MIME, b"whatever") is None
    assert extract_content(DOCX_MIME, b"not a real docx") is None


# --- local document source ---


def test_local_source_walks_extracts_and_skips(tmp_path):
    """Supported files normalized at the edge, the rest skipped."""
    clients = tmp_path / "Clients" / "Techni-Pneus"
    clients.mkdir(parents=True)
    (clients / "notes.md").write_text("Delivery planned for March.")
    (clients / "photo.png").write_bytes(b"\x89PNG")
    (clients / "tracking.xlsx").write_bytes(b"fake sheet")

    documents = {doc.title: doc for doc in LocalDocumentSource(str(tmp_path)).fetch()}

    assert set(documents) == {"notes.md", "tracking.xlsx"}
    notes = documents["notes.md"]
    assert notes.folder_path == "Clients/Techni-Pneus"
    assert notes.origin_ref == "local:Clients/Techni-Pneus/notes.md"
    assert "March" in notes.text
    assert notes.web_view_link is None
    assert documents["tracking.xlsx"].text is None  # cataloged, never extracted


# --- API surface ---


def make_service(app, documents):
    """A DarrylService on scripted seams, mounted via dependency override."""
    from backend.app.db.session import build_engine, build_session_factory
    from backend.app.db.init_db import init_db
    from backend.app.config import get_settings

    engine = build_engine(get_settings().database_url)
    init_db(engine)
    service = DarrylService(
        source=FakeDocumentSource(documents),
        llm=ScriptedLLMProvider(['{"tags": []}'] * len(documents)),
        session_factory=build_session_factory(engine),
        vector_store=FakeVectorStore(),
    )
    app.dependency_overrides[get_darryl_service] = lambda: service
    return service


def test_darryl_endpoints_roundtrip(app, client):
    """Sync, audit strip, bin, one-click filing - the overlay's contract."""
    make_service(app, [source_doc(folder_path="Misc", title="mystery.pdf")])

    report = client.post("/api/v1/darryl/sync").json()
    assert report["added"] == 1 and report["unclassified"] == 1

    recent = client.get("/api/v1/darryl/documents/recent?limit=5").json()
    assert [d["title"] for d in recent] == ["mystery.pdf"]
    binned = client.get("/api/v1/darryl/documents/unclassified").json()
    assert [d["status"] for d in binned] == ["unclassified"]

    # Closed world over HTTP: an unknown target is a 422.
    bad = client.post(
        f"/api/v1/darryl/documents/{binned[0]['id']}/classify",
        json={"entity_type": "client", "entity_id": 999},
    )
    assert bad.status_code == 422
    missing = client.post(
        "/api/v1/darryl/documents/424242/classify",
        json={"entity_type": "client", "entity_id": 1},
    )
    assert missing.status_code == 404
