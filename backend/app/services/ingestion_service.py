"""Ingestion: pull documents from a source, run each through Tell Dwight.

There is exactly one capture pipeline in Scranton. An ingested Drive
document takes the same path as a hand-typed note: entries, proposed
segments, manager validation. This service is only the loop in between.
"""

from backend.app.adapters.ingestion.base import IngestionSource
from backend.app.domain.schemas import EntryCreate, IngestSummary
from backend.app.services.dwight_service import DwightProcessingError, DwightService


class IngestionService:
    """Feed every document of a source to the Dwight pipeline."""

    def __init__(self, source: IngestionSource, dwight: DwightService) -> None:
        """Wire the source and the one capture pipeline."""
        self.source = source
        self.dwight = dwight

    def run(self) -> IngestSummary:
        """Process the whole source, one document at a time.

        Synchronous on purpose for the POC (a demo folder holds a
        handful of files). A failing document is counted and skipped,
        never fatal: its raw text is already safe in entries anyway.
        """
        summary = IngestSummary()
        for document in self.source.fetch():
            summary.documents += 1
            try:
                result = self.dwight.capture(
                    EntryCreate(
                        raw_content=document.content,
                        source_type=document.source_type,
                    )
                )
            except DwightProcessingError:
                summary.failures += 1
                continue
            summary.entry_ids.append(result.entry_id)
            if result.clarification:
                summary.clarifications += 1
        return summary
