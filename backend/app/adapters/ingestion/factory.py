"""Ingestion source selection: one entry point, sources plug in over time."""

from backend.app.adapters.ingestion.base import IngestionSource
from backend.app.adapters.ingestion.local import LocalSource
from backend.app.config import Settings


def build_ingestion_source(settings: Settings) -> IngestionSource:
    """Return the configured ingestion source.

    Only LocalSource exists for now. The Google Drive connector (MLP) and
    later sources plug in here, selected by configuration, without any
    change for the callers.
    """
    return LocalSource()
