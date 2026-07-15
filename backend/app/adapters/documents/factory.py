"""Document source selection: one entry point, connectors plug in over time."""

from backend.app.adapters.documents.base import DocumentSource
from backend.app.adapters.documents.gdrive import GDriveDocumentSource
from backend.app.adapters.documents.local import LocalDocumentSource
from backend.app.config import Settings


def build_document_source(settings: Settings) -> DocumentSource:
    """Return the configured corpus connector.

    The connector registry of the documentary side: Notion, Teams,
    Slack and GMail each become one adapter plus one branch here
    (owner, 2026-07-15) - callers never change.
    """
    if settings.darryl_source == "local":
        return LocalDocumentSource(root_dir=settings.darryl_local_dir)
    if settings.darryl_source == "gdrive":
        return GDriveDocumentSource(
            client_secrets_file=settings.google_client_secrets,
            token_file=settings.google_token_file,
            folder_id=settings.gdrive_folder_id,
        )
    raise ValueError(f"Unknown document source kind {settings.darryl_source!r}.")
