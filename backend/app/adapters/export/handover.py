"""Handover fiche renderers: the printable, signable artifact.

Not on the summary Exporter seam on purpose: a handover is not a
SummaryResponse, and its layout carries legal weight (two blocks, a
withheld count, a two-party signature area). Same output philosophy
though: zero dependencies, markdown + standalone printable HTML.
"""

from html import escape

from backend.app.adapters.export.base import ExportFile, slugify
from backend.app.domain.schemas import (
    HandoverDossier,
    HandoverItem,
    HandoverValidationOut,
)

SIGNATURE_NOTE = (
    "Both parties reviewed this document together. The employee saw every "
    "disclosed observation before transmission (GDPR right of access)."
)

# Same print-first styling family as the summary export: white paper,
# IBM Plex, restrained ink. Inline so the file stands alone.
HTML_STYLE = """\
body { font-family: 'IBM Plex Sans', -apple-system, sans-serif; color: #1a1a1a;
       max-width: 720px; margin: 40px auto; padding: 0 24px; line-height: 1.6; }
h1 { font-weight: 900; font-size: 26px; margin-bottom: 4px; }
.subtitle { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #666;
            margin-bottom: 28px; }
h2 { font-family: 'IBM Plex Mono', monospace; font-size: 13px; letter-spacing: 1px;
     text-transform: uppercase; color: #444; border-bottom: 1px solid #ddd;
     padding-bottom: 4px; margin: 26px 0 8px; }
.item { margin-bottom: 10px; }
.meta { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: #888; }
.withheld { font-style: italic; color: #666; }
.signatures { margin-top: 42px; border-top: 1px solid #ddd; padding-top: 16px; }
.signatures p { font-size: 12px; color: #444; }
.sign-line { display: inline-block; width: 45%; margin-top: 34px;
             border-top: 1px solid #1a1a1a; font-family: 'IBM Plex Mono', monospace;
             font-size: 11px; color: #444; }
.sign-line + .sign-line { margin-left: 8%; }
@media print { body { margin: 0 auto; } }"""


def handover_filename(dossier: HandoverDossier, extension: str) -> str:
    """scranton_handover_<member>_<date>.<ext>: tidy and sortable."""
    return (
        f"scranton_handover_{slugify(dossier.member_name)}"
        f"_{dossier.generated_at:%Y%m%d}.{extension}"
    )


def _item_line(item: HandoverItem) -> str:
    """One verbatim item as markdown: date, sensitivity, topics, text."""
    topics = f" ({'; '.join(item.topics)})" if item.topics else ""
    return (
        f"- ({item.created_at:%Y-%m-%d}) [sensitivity {item.sensitivity_level}/5]"
        f"{topics}\n  {item.content}"
    )


def _signed(validation: HandoverValidationOut | None) -> bool:
    """Whether the fiche carries typed signatures instead of blank lines."""
    return validation is not None and validation.validated_at is not None


def _md_signature_lines(validation: HandoverValidationOut | None) -> list[str]:
    """Blank paper lines before signature, typed names + timestamps after.

    The hash itself is never rendered into the fiche (it hashes the
    fiche, so it cannot be part of it); it lives in the consent record.
    """
    if not _signed(validation):
        return [
            "Outgoing manager: ______________________  date: __________",
            "",
            "Team member:      ______________________  date: __________",
        ]
    return [
        f"Outgoing manager: {validation.manager_signature_name}  "
        f"signed: {validation.manager_signed_at:%Y-%m-%d %H:%M} UTC",
        "",
        f"Team member:      {validation.member_signature_name}  "
        f"signed: {validation.member_signed_at:%Y-%m-%d %H:%M} UTC",
    ]


def render_markdown(
    dossier: HandoverDossier, validation: HandoverValidationOut | None = None
) -> ExportFile:
    """The fiche as .md: two blocks, withheld count, signature block."""
    withheld = (
        [
            f"*{dossier.excluded_warm_count} observation(s) withheld by the "
            "outgoing manager - the count travels, the content does not.*",
            "",
        ]
        if dossier.excluded_warm_count
        else []
    )
    lines = [
        f"# Transfer to Philly - {dossier.member_name}",
        "",
        f"> {dossier.member_role or 'Team member'} - generated "
        f"{dossier.generated_at:%Y-%m-%d %H:%M} UTC - "
        f"{dossier.schema_id} v{dossier.schema_version}",
        "> Verbatim validated segments. Assembled by Scranton, no model rewriting.",
        "",
        "## Cold data (objective facts - transmissible)",
        "",
        *([_item_line(item) for item in dossier.cold] or ["*Nothing recorded.*"]),
        "",
        "## Warm data (manager observations - disclosed selection)",
        "",
        *([_item_line(item) for item in dossier.warm] or ["*Nothing disclosed.*"]),
        "",
        *withheld,
        "## Validation",
        "",
        SIGNATURE_NOTE,
        "",
        *_md_signature_lines(validation),
        "",
    ]
    return ExportFile(
        filename=handover_filename(dossier, "md"),
        media_type="text/markdown; charset=utf-8",
        content="\n".join(lines).encode("utf-8"),
    )


def _item_html(item: HandoverItem) -> str:
    """One verbatim item as escaped HTML."""
    topics = f" - {escape('; '.join(item.topics))}" if item.topics else ""
    return (
        f'<div class="item"><span class="meta">({item.created_at:%Y-%m-%d}) '
        f"sensitivity {item.sensitivity_level}/5{topics}</span><br />"
        f"{escape(item.content)}</div>"
    )


def _html_signature_lines(validation: HandoverValidationOut | None) -> str:
    """The two sign-line spans, blank or carrying the typed signatures."""
    if not _signed(validation):
        return (
            '<span class="sign-line">Outgoing manager - date</span>'
            '<span class="sign-line">Team member - date</span>'
        )
    return (
        f'<span class="sign-line">Outgoing manager - '
        f"{escape(validation.manager_signature_name)} - "
        f"signed {validation.manager_signed_at:%Y-%m-%d %H:%M} UTC</span>"
        f'<span class="sign-line">Team member - '
        f"{escape(validation.member_signature_name)} - "
        f"signed {validation.member_signed_at:%Y-%m-%d %H:%M} UTC</span>"
    )


def render_html(
    dossier: HandoverDossier, validation: HandoverValidationOut | None = None
) -> ExportFile:
    """The fiche as a standalone printable page, everything escaped."""
    cold = "".join(_item_html(item) for item in dossier.cold) or (
        '<p class="withheld">Nothing recorded.</p>'
    )
    warm = "".join(_item_html(item) for item in dossier.warm) or (
        '<p class="withheld">Nothing disclosed.</p>'
    )
    withheld = (
        f'<p class="withheld">{dossier.excluded_warm_count} observation(s) '
        "withheld by the outgoing manager - the count travels, the content "
        "does not.</p>"
        if dossier.excluded_warm_count
        else ""
    )
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8" />'
        f"<title>Transfer to Philly - {escape(dossier.member_name)}</title>"
        f"<style>{HTML_STYLE}</style></head><body>"
        f"<h1>Transfer to Philly - {escape(dossier.member_name)}</h1>"
        f'<p class="subtitle">{escape(dossier.member_role or "Team member")} - '
        f"generated {dossier.generated_at:%Y-%m-%d %H:%M} UTC - "
        f"{dossier.schema_id} v{dossier.schema_version}</p>"
        f"<h2>Cold data (objective facts - transmissible)</h2>{cold}"
        f"<h2>Warm data (manager observations - disclosed selection)</h2>{warm}"
        f"{withheld}"
        f'<div class="signatures"><p>{escape(SIGNATURE_NOTE)}</p>'
        f"{_html_signature_lines(validation)}</div>"
        "</body></html>"
    )
    return ExportFile(
        filename=handover_filename(dossier, "html"),
        media_type="text/html; charset=utf-8",
        content=document.encode("utf-8"),
    )


HANDOVER_RENDERERS = {"md": render_markdown, "html": render_html}
