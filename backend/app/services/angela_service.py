"""Send Angela: one-click export. No retyping. No questions asked.

Angela owns nothing: she asks the summary engine for the document and
an exporter for the file. Formats live in a registry - a new format
(PDF, Grist, Docs) is one adapter plus one entry, and Angela's logic
never changes.
"""

from backend.app.adapters.export.base import Exporter, ExportFile
from backend.app.adapters.export.html import HtmlExporter
from backend.app.adapters.export.markdown import MarkdownExporter
from backend.app.services.summary_service import SummaryService

EXPORTERS: dict[str, Exporter] = {
    "md": MarkdownExporter(),
    "html": HtmlExporter(),
}


class UnknownFormatError(Exception):
    """No exporter registered for that format key."""


class AngelaService:
    """Generate the summary, render the file, deliver."""

    def __init__(self, summary_service: SummaryService) -> None:
        """Angela stands on the summary engine: same gates, same sources."""
        self.summary_service = summary_service

    def export(
        self, template_id: str, target_id: int | None, format_key: str
    ) -> ExportFile:
        """One click: assemble the living summary and render it as a file.

        Summary errors (unknown template, missing target...) bubble up
        unchanged: the API layer already knows how to translate them.
        """
        exporter = EXPORTERS.get(format_key)
        if exporter is None:
            known = ", ".join(sorted(EXPORTERS))
            raise UnknownFormatError(
                f"Unknown export format {format_key!r} (available: {known})."
            )
        summary = self.summary_service.generate(template_id, target_id)
        return exporter.render(summary)
