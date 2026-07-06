"""Exporter: the output seam (ARCHITECTURE_SKETCH section 13).

Formatting never happens inside services: a summary becomes a file
here, and only here. Markdown and printable HTML are the POC
implementations; PDF generation, Grist Core or Docs (LaSuite) plug in
as new adapters without touching Angela's logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from backend.app.domain.schemas import SummaryResponse


@dataclass(frozen=True)
class ExportFile:
    """One rendered export, ready to be delivered."""

    filename: str
    media_type: str
    content: bytes


class Exporter(ABC):
    """Abstract contract: render a summary into a downloadable file."""

    @abstractmethod
    def render(self, summary: SummaryResponse) -> ExportFile:
        """Turn one living summary into a file."""


def slugify(text: str) -> str:
    """A filesystem-safe slug for filenames: lowercase, hyphens only."""
    cleaned = "".join(
        char if char.isalnum() else "-" for char in text.lower()
    ).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "summary"


def export_filename(summary: SummaryResponse, extension: str) -> str:
    """scranton_<template>_<target>_<date>.<ext>: tidy, sortable, Angela-approved."""
    parts = ["scranton", summary.template_id]
    if summary.target_label:
        parts.append(slugify(summary.target_label))
    parts.append(f"{summary.generated_at:%Y%m%d}")
    return "_".join(parts) + f".{extension}"
