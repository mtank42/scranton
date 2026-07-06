"""Printable HTML exporter: the POC's road to PDF without a PDF library.

A standalone, print-friendly page: open it, Cmd+P, done. A real PDF
generator can join the registry later as its own adapter; this one
costs zero dependencies.
"""

from html import escape

from backend.app.adapters.export.base import Exporter, ExportFile, export_filename
from backend.app.domain.schemas import SummaryResponse

# Print-first styling: white paper, IBM Plex (the design system fonts),
# restrained ink. Inline on purpose: the file must stand alone.
STYLE = """\
body { font-family: 'IBM Plex Sans', -apple-system, sans-serif; color: #1a1a1a;
       max-width: 720px; margin: 40px auto; padding: 0 24px; line-height: 1.6; }
h1 { font-weight: 900; font-size: 26px; margin-bottom: 4px; }
.subtitle { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #666;
            margin-bottom: 28px; }
h2 { font-family: 'IBM Plex Mono', monospace; font-size: 13px; letter-spacing: 1px;
     text-transform: uppercase; color: #444; border-bottom: 1px solid #ddd;
     padding-bottom: 4px; margin: 26px 0 8px; }
ol { padding-left: 20px; } li { font-size: 13px; color: #444; margin-bottom: 4px; }
.footer { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: #999;
          margin-top: 36px; }
@media print { body { margin: 0 auto; } }"""


class HtmlExporter(Exporter):
    """Render a summary as a standalone printable HTML page."""

    def render(self, summary: SummaryResponse) -> ExportFile:
        """Everything escaped: summary content is model- and user-authored."""
        title = escape(summary.title) + (
            f" - {escape(summary.target_label)}" if summary.target_label else ""
        )
        subtitle = escape(
            " - ".join(
                part
                for part in (
                    f"last {summary.window_days} days" if summary.window_days else "full history",
                    f"generated {summary.generated_at:%Y-%m-%d %H:%M} UTC",
                )
                if part
            )
        )
        sections = "".join(
            f"<h2>{escape(section.heading)}</h2><p>{escape(section.content)}</p>"
            for section in summary.sections
        )
        sources = ""
        if summary.sources:
            items = "".join(
                f"<li>({source.created_at:%Y-%m-%d}) [{source.data_type.value}] "
                f"{escape(source.content)}</li>"
                for source in summary.sources
            )
            sources = f"<h2>Sources</h2><ol>{items}</ol>"
        document = (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\" />"
            f"<title>{title}</title><style>{STYLE}</style></head><body>"
            f"<h1>{title}</h1><p class=\"subtitle\">{subtitle}</p>"
            f"{sections}{sources}"
            "<p class=\"footer\">Assembled by Scranton from the validated memory. "
            "Delivered by Send Angela.</p>"
            "</body></html>"
        )
        return ExportFile(
            filename=export_filename(summary, "html"),
            media_type="text/html; charset=utf-8",
            content=document.encode("utf-8"),
        )
