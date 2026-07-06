"""Ingestion source selection: one entry point, sources plug in over time."""

from backend.app.adapters.ingestion.base import IngestionSource
from backend.app.adapters.ingestion.gdrive import GDriveSource
from backend.app.adapters.ingestion.local import LocalSource
from backend.app.config import Settings


def build_ingestion_source(settings: Settings, kind: str = "local") -> IngestionSource:
    """Return an ingestion source by kind.

    The connector registry in its simplest form: WhatsApp export, Apple
    Notes, Dropbox and the rest each become one adapter plus one branch
    here - callers never change.
    """
    if kind == "local":
        return LocalSource()
    if kind == "gdrive":
        return GDriveSource(
            client_secrets_file=settings.google_client_secrets,
            token_file=settings.google_token_file,
            folder_id=settings.gdrive_folder_id,
        )
    raise ValueError(f"Unknown ingestion source kind {kind!r}.")
