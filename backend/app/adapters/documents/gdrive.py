"""Google Drive connector for the documentary corpus.

Walks the shared folder RECURSIVELY (the Dwight-gate connector reads
one flat folder; a real corpus is a tree - 'Clients/Techni-Pneus/2026').
Google-native documents and presentations are exported as plain text;
binary office formats are downloaded and run through the extraction
registry; spreadsheets are cataloged without download (owner
arbitration, 2026-07-15). Reuses the read-only OAuth material of the
existing Drive setup: one consent covers both connectors.
"""

import hashlib
from collections.abc import Iterable
from datetime import datetime

from googleapiclient.discovery import build

from backend.app.adapters.documents.base import DocumentSource, SourceDocument
from backend.app.adapters.extraction.registry import (
    extract_content,
    is_catalog_only,
    is_supported,
)
from backend.app.adapters.ingestion.gdrive import MissingCredentialsError, load_credentials

FOLDER_MIME = "application/vnd.google-apps.folder"
# Google-native formats have no bytes to download: they are exported.
EXPORTED_MIMES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.presentation",
}
LIST_FIELDS = "nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink)"


class GDriveDocumentSource(DocumentSource):
    """Yields every supported document under one shared Drive folder."""

    def __init__(self, client_secrets_file: str, token_file: str, folder_id: str) -> None:
        """Store configuration only: no network, no auth at construction."""
        self.client_secrets_file = client_secrets_file
        self.token_file = token_file
        self.folder_id = folder_id

    def _drive(self):
        """Build the Drive API client. Overridden with a fake in tests."""
        credentials = load_credentials(self.client_secrets_file, self.token_file)
        return build("drive", "v3", credentials=credentials)

    def fetch(self) -> Iterable[SourceDocument]:
        """Walk the shared folder tree, normalizing at the edge."""
        if not self.folder_id:
            raise MissingCredentialsError(
                "GDRIVE_FOLDER_ID is not configured. Set it in .env "
                "(the folder id is the last part of the Drive folder URL)."
            )
        drive = self._drive()
        yield from self._walk(drive, self.folder_id, folder_path="")

    def _walk(self, drive, folder_id: str, folder_path: str) -> Iterable[SourceDocument]:
        """Yield the supported files of one folder, then recurse."""
        for file in self._list_children(drive, folder_id):
            if file["mimeType"] == FOLDER_MIME:
                child_path = f"{folder_path}/{file['name']}" if folder_path else file["name"]
                yield from self._walk(drive, file["id"], child_path)
                continue
            document = self._normalize(drive, file, folder_path)
            if document is not None:
                yield document

    @staticmethod
    def _list_children(drive, folder_id: str) -> list[dict]:
        """One folder's direct children, all pages."""
        files: list[dict] = []
        token = None
        while True:
            response = (
                drive.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields=LIST_FIELDS,
                    pageToken=token,
                )
                .execute()
            )
            files.extend(response.get("files", []))
            token = response.get("nextPageToken")
            if not token:
                return files

    def _normalize(self, drive, file: dict, folder_path: str) -> SourceDocument | None:
        """Build one SourceDocument, or None for unsupported formats."""
        mime_type = file["mimeType"]
        exported = mime_type in EXPORTED_MIMES
        if not exported and not is_supported(mime_type):
            return None  # images and the rest: skipped, never fatal

        if is_catalog_only(mime_type):
            # No download: the catalog entry only needs identity and
            # freshness, so the fingerprint is the modification time.
            data, text = None, None
            sha = hashlib.sha256(
                f"{file['id']}:{file.get('modifiedTime', '')}".encode()
            ).hexdigest()
        elif exported:
            data = drive.files().export(fileId=file["id"], mimeType="text/plain").execute()
            text = data.decode("utf-8", errors="replace")
            sha = hashlib.sha256(data).hexdigest()
        else:
            data = drive.files().get_media(fileId=file["id"]).execute()
            text = extract_content(mime_type, data)
            sha = hashlib.sha256(data).hexdigest()

        modified = file.get("modifiedTime")
        return SourceDocument(
            origin_ref=f"gdrive:{file['id']}",
            title=file["name"],
            mime_type=mime_type,
            folder_path=folder_path,
            # Drive timestamps are RFC 3339 with a Z suffix.
            modified_at=datetime.fromisoformat(modified.replace("Z", "+00:00"))
            if modified
            else None,
            web_view_link=file.get("webViewLink"),
            content_sha256=sha,
            text=text,
        )
