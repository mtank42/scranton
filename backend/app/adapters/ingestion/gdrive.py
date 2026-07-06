"""Google Drive connector (MLP): the first real IngestionSource.

Reads one configured Drive folder, pulls Google Docs (exported as plain
text) and plain-text files, and normalizes everything to RawDoc - so
the Tell Dwight pipeline never knows Drive exists. PDFs and other
binary formats are out of scope for the POC (skipped, not failed).

One-time setup on the owner's machine: docs/google_drive_ingestion.md.
Privacy note: Drive is a tester-onboarding convenience; sovereign and
local ingestion remain the V2 product target.
"""

from collections.abc import Iterable
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from backend.app.adapters.ingestion.base import IngestionSource
from backend.app.domain.models import SourceType
from backend.app.domain.schemas import RawDoc

# Read-only: the connector must never be able to touch the user's files.
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
TEXT_MIMES = {"text/plain", "text/markdown"}


class MissingCredentialsError(Exception):
    """OAuth client secrets are not configured yet (see the setup doc)."""


class GDriveSource(IngestionSource):
    """Pulls documents from a single Drive folder, normalized to RawDoc."""

    def __init__(self, client_secrets_file: str, token_file: str, folder_id: str) -> None:
        """Store configuration only: no network, no auth at construction."""
        self.client_secrets_file = client_secrets_file
        self.token_file = token_file
        self.folder_id = folder_id

    # --- auth ---

    def _credentials(self) -> Credentials:
        """Load, refresh, or interactively obtain OAuth credentials.

        The first run opens a browser for consent (installed-app flow)
        and caches the token under data/. Subsequent runs refresh
        silently. This is a local-first, single-user POC: a web-based
        consent flow becomes necessary only with hosted multi-user (V2).
        """
        credentials = None
        if Path(self.token_file).exists():
            credentials = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        elif not credentials or not credentials.valid:
            if not Path(self.client_secrets_file).exists():
                raise MissingCredentialsError(
                    f"Google OAuth client secrets not found at {self.client_secrets_file}. "
                    "See docs/google_drive_ingestion.md for the one-time setup."
                )
            flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_file, SCOPES)
            credentials = flow.run_local_server(port=0)
        Path(self.token_file).write_text(credentials.to_json())
        return credentials

    def _drive(self):
        """Build the Drive API client. Overridden with a fake in tests."""
        return build("drive", "v3", credentials=self._credentials())

    # --- fetch ---

    def fetch(self) -> Iterable[RawDoc]:
        """Yield every supported document of the folder as a RawDoc."""
        if not self.folder_id:
            raise MissingCredentialsError(
                "GDRIVE_FOLDER_ID is not configured. Set it in .env "
                "(the folder id is the last part of the Drive folder URL)."
            )
        drive = self._drive()
        response = (
            drive.files()
            .list(
                q=f"'{self.folder_id}' in parents and trashed = false",
                fields="files(id, name, mimeType)",
            )
            .execute()
        )
        for file in response.get("files", []):
            content = self._read(drive, file)
            if content is None:
                continue  # unsupported format: skipped, never fatal
            yield RawDoc(
                content=content,
                source_type=SourceType.NOTE,
                origin_ref=f"gdrive:{file['id']}:{file['name']}",
            )

    @staticmethod
    def _read(drive, file: dict) -> str | None:
        """Return the text of one Drive file, or None if unsupported."""
        if file["mimeType"] == GOOGLE_DOC_MIME:
            raw = drive.files().export(fileId=file["id"], mimeType="text/plain").execute()
            return raw.decode("utf-8")
        if file["mimeType"] in TEXT_MIMES:
            raw = drive.files().get_media(fileId=file["id"]).execute()
            return raw.decode("utf-8")
        return None
