"""DocumentSource: the connector seam of the documentary corpus.

Distinct from IngestionSource on purpose: that seam normalizes raw text
for the Tell Dwight gate (human input), while this one feeds Darryl -
documents validated by the sharing gesture itself, carrying the
metadata the corpus lives on (path, dates, links). Notion, Teams,
Slack and GMail become adapters here later (owner, 2026-07-15).

'Normalize at the edge' still applies: extraction happens source-side
(through the extraction registry), so the Darryl pipeline only ever
sees SourceDocument and never knows where a file came from.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class SourceDocument:
    """One shared document, normalized at the source edge.

    text is the extracted content, or None when the format is cataloged
    without content (spreadsheets) or extraction failed - the document
    still enters the corpus as a catalog entry either way.
    """

    origin_ref: str
    title: str
    mime_type: str
    # Path of the containing folder relative to the shared root
    # ('' at the root): Darryl's first routing signal.
    folder_path: str
    modified_at: datetime | None
    web_view_link: str | None
    # Fingerprint of the source content: resync re-extracts only when
    # it changes.
    content_sha256: str
    text: str | None


class DocumentSource(ABC):
    """Abstract contract: enumerate the shared corpus, normalized."""

    @abstractmethod
    def fetch(self) -> Iterable[SourceDocument]:
        """Yield every supported document currently in the source.

        The FULL current picture, every call: the sync diffs it against
        the database to detect additions, changes and removals. Files
        in unsupported formats are skipped at the edge, never yielded.
        """
