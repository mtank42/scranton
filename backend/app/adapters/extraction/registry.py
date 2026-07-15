"""ContentExtractor registry: MIME type -> plain text.

The extraction seam of the Darryl pipeline: one narrow function per
format, registered in a dict. Adding a format is one entry here, never
a pipeline change. Spreadsheets are deliberately ABSENT from the
extractors: the owner's arbitration (2026-07-15) catalogs them by name,
date, folder and link - their content flattened to text is mush, not
memory.

Imports of the format libraries are local to each extractor: the app
boots (and the offline tests run) without touching pypdf, python-docx
or python-pptx until a real document of that format shows up.
"""

import io
from collections.abc import Callable

# Long official MIME identifiers, named once.
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
TEXT_MIMES = ("text/plain", "text/markdown")

# Cataloged, never content-extracted (see module docstring).
CATALOG_ONLY_MIMES = frozenset(
    {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.google-apps.spreadsheet",
    }
)


def _extract_pdf(data: bytes) -> str:
    """Concatenate the text layer of every page."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    """Concatenate every paragraph of a Word document."""
    from docx import Document

    return "\n".join(paragraph.text for paragraph in Document(io.BytesIO(data)).paragraphs)


def _extract_pptx(data: bytes) -> str:
    """Concatenate the text frames of every slide, slide order preserved."""
    from pptx import Presentation

    lines: list[str] = []
    for slide in Presentation(io.BytesIO(data)).slides:
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text:
                lines.append(shape.text_frame.text)
    return "\n".join(lines)


def _extract_text(data: bytes) -> str:
    """Plain text and markdown: decode, tolerating stray bytes."""
    return data.decode("utf-8", errors="replace")


EXTRACTORS: dict[str, Callable[[bytes], str]] = {
    PDF_MIME: _extract_pdf,
    DOCX_MIME: _extract_docx,
    PPTX_MIME: _extract_pptx,
    **{mime: _extract_text for mime in TEXT_MIMES},
}


def is_catalog_only(mime_type: str) -> bool:
    """True when the format is cataloged (metadata + link), not indexed."""
    return mime_type in CATALOG_ONLY_MIMES


def is_supported(mime_type: str) -> bool:
    """True when Darryl has any business with this format at all."""
    return mime_type in EXTRACTORS or is_catalog_only(mime_type)


def extract_content(mime_type: str, data: bytes) -> str | None:
    """Return the plain text of a document, or None when not extractable.

    None covers both the catalog-only formats and extraction failures
    (a corrupt file must never fail a whole sync): the caller catalogs
    the document either way, so nothing shared is ever silently lost.
    """
    extractor = EXTRACTORS.get(mime_type)
    if extractor is None:
        return None
    try:
        return extractor(data)
    except Exception:
        return None
