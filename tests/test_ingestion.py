"""Ingestion: the Drive connector (on a fake Drive) and the pipeline loop."""

import json

import pytest

from backend.app.adapters.ingestion.base import IngestionSource
from backend.app.adapters.ingestion.gdrive import GDriveSource, MissingCredentialsError
from backend.app.domain.models import Entry, SourceType
from backend.app.domain.schemas import RawDoc
from backend.app.services.dwight_service import DwightService
from backend.app.services.ingestion_service import IngestionService
from tests.conftest import FakeVectorStore, ScriptedLLMProvider
from tests.test_dwight_service import TWO_SEGMENT_PROPOSAL


class FakeRequest:
    """Mimics a googleapiclient request: .execute() returns the payload."""

    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeFiles:
    """Mimics drive.files(): canned folder listing and file contents."""

    def __init__(self):
        self.listing = {
            "files": [
                {"id": "doc1", "name": "1:1 notes", "mimeType": "application/vnd.google-apps.document"},
                {"id": "txt1", "name": "todo.txt", "mimeType": "text/plain"},
                {"id": "img1", "name": "team.png", "mimeType": "image/png"},
            ]
        }

    def list(self, **kwargs):
        return FakeRequest(self.listing)

    def export(self, fileId, mimeType):
        return FakeRequest(f"google doc {fileId}".encode())

    def get_media(self, fileId):
        return FakeRequest(f"plain text {fileId}".encode())


class FakeDrive:
    """Mimics the drive v3 client surface used by GDriveSource."""

    def files(self):
        return FakeFiles()


class ListSource(IngestionSource):
    """An in-memory source for pipeline-loop tests."""

    def __init__(self, docs: list[RawDoc]):
        self.docs = docs

    def fetch(self):
        yield from self.docs


def make_gdrive(tmp_path, folder_id="folder-1") -> GDriveSource:
    """A GDriveSource on throwaway paths, Drive client replaced by a fake."""
    source = GDriveSource(
        client_secrets_file=str(tmp_path / "secrets.json"),
        token_file=str(tmp_path / "token.json"),
        folder_id=folder_id,
    )
    source._drive = lambda: FakeDrive()
    return source


def test_gdrive_normalizes_supported_files_and_skips_the_rest(tmp_path):
    """Google Docs and text files become RawDoc; the image is skipped."""
    docs = list(make_gdrive(tmp_path).fetch())

    assert [d.origin_ref for d in docs] == ["gdrive:doc1:1:1 notes", "gdrive:txt1:todo.txt"]
    assert docs[0].content == "google doc doc1"
    assert docs[1].content == "plain text txt1"
    assert all(d.source_type == SourceType.NOTE for d in docs)


def test_gdrive_without_folder_id_fails_with_setup_pointer(tmp_path):
    """A missing folder id is a configuration error with guidance."""
    with pytest.raises(MissingCredentialsError, match="GDRIVE_FOLDER_ID"):
        list(make_gdrive(tmp_path, folder_id="").fetch())


def test_gdrive_without_secrets_points_to_the_setup_doc(tmp_path):
    """No token, no secrets file: the error names the doc to read."""
    source = GDriveSource(
        client_secrets_file=str(tmp_path / "missing.json"),
        token_file=str(tmp_path / "token.json"),
        folder_id="folder-1",
    )
    with pytest.raises(MissingCredentialsError, match="google_drive_ingestion"):
        source._credentials()


def test_ingestion_runs_every_document_through_dwight(session_factory):
    """Two documents in, two entries with proposed segments out."""
    llm = ScriptedLLMProvider([TWO_SEGMENT_PROPOSAL, TWO_SEGMENT_PROPOSAL])
    dwight = DwightService(
        llm=llm, session_factory=session_factory, vector_store=FakeVectorStore()
    )
    source = ListSource(
        [
            RawDoc(content="first doc", source_type=SourceType.NOTE, origin_ref="a"),
            RawDoc(content="second doc", source_type=SourceType.NOTE, origin_ref="b"),
        ]
    )

    summary = IngestionService(source, dwight).run()

    assert summary.documents == 2
    assert len(summary.entry_ids) == 2
    assert summary.failures == 0
    with session_factory() as session:
        assert session.query(Entry).count() == 2


def test_a_failing_document_is_counted_and_skipped(session_factory):
    """One bad model answer does not stop the pull; the raw text is safe."""
    llm = ScriptedLLMProvider(["bad", "still bad", TWO_SEGMENT_PROPOSAL])
    dwight = DwightService(
        llm=llm, session_factory=session_factory, vector_store=FakeVectorStore()
    )
    source = ListSource(
        [
            RawDoc(content="fails", source_type=SourceType.NOTE, origin_ref="a"),
            RawDoc(content="works", source_type=SourceType.NOTE, origin_ref="b"),
        ]
    )

    summary = IngestionService(source, dwight).run()

    assert summary.documents == 2
    assert summary.failures == 1
    assert len(summary.entry_ids) == 1
    with session_factory() as session:
        # Both raw texts persisted: the failing one stays pending.
        assert session.query(Entry).count() == 2


def test_endpoint_maps_missing_setup_to_503(app, client, monkeypatch):
    """Without configuration the endpoint answers 503 with guidance.

    The first missing piece (the folder id here) names itself: setup
    errors must always tell the user what to do next.
    """
    monkeypatch.delenv("GDRIVE_FOLDER_ID", raising=False)
    response = client.post("/api/v1/ingest/gdrive")
    assert response.status_code == 503
    assert "GDRIVE_FOLDER_ID" in response.json()["detail"]