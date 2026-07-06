"""Markdown exporter: the universal, tool-agnostic format.

Markdown pastes into anything (mail, Notion, Docs, a ticket), which is
the whole point of Send Angela: no retyping, ever.
"""

from backend.app.adapters.export.base import Exporter, ExportFile, export_filename
from backend.app.domain.schemas import SummaryResponse


class MarkdownExporter(Exporter):
    """Render a summary as a plain .md document."""

    def render(self, summary: SummaryResponse) -> ExportFile:
        """Title, provenance line, sections as headings, numbered sources."""
        subtitle = " - ".join(
            part
            for part in (
                summary.target_label,
                f"last {summary.window_days} days" if summary.window_days else "full history",
                f"generated {summary.generated_at:%Y-%m-%d %H:%M} UTC",
            )
            if part
        )
        lines = [
            f"# {summary.title}" + (f" - {summary.target_label}" if summary.target_label else ""),
            "",
            f"> {subtitle}",
            "> Assembled by Scranton from the validated memory. Delivered by Send Angela.",
            "",
        ]
        for section in summary.sections:
            lines += [f"## {section.heading}", "", section.content, ""]
        if summary.sources:
            lines += ["## Sources", ""]
            lines += [
                f"{i}. ({source.created_at:%Y-%m-%d}) [{source.data_type.value}] {source.content}"
                for i, source in enumerate(summary.sources, start=1)
            ]
            lines.append("")
        return ExportFile(
            filename=export_filename(summary, "md"),
            media_type="text/markdown; charset=utf-8",
            content="\n".join(lines).encode("utf-8"),
        )
