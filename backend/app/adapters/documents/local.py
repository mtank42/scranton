"""Local folder connector: the sovereign DocumentSource.

Walks one directory tree on disk. This is both the test workhorse and
the local-first path: a folder synced by any means (Syncthing, a NAS
mount, iCloud) becomes a corpus without any cloud API. No web links:
web_view_link stays None for local files.
"""

import hashlib
import mimetypes
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from backend.app.adapters.documents.base import DocumentSource, SourceDocument
from backend.app.adapters.extraction.registry import extract_content, is_supported

# Office formats mimetypes.guess_type does not know on every platform.
EXTENSION_MIMES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".md": "text/markdown",
}


def guess_mime(path: Path) -> str | None:
    """MIME type from the file extension, office formats included."""
    explicit = EXTENSION_MIMES.get(path.suffix.lower())
    if explicit:
        return explicit
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed


class LocalDocumentSource(DocumentSource):
    """Yields every supported file under one root directory."""

    def __init__(self, root_dir: str) -> None:
        """Store the root; existence is checked at fetch time."""
        self.root_dir = root_dir

    def fetch(self) -> Iterable[SourceDocument]:
        """Walk the tree, extract at the edge, skip unsupported formats."""
        root = Path(self.root_dir)
        if not self.root_dir or not root.is_dir():
            raise FileNotFoundError(
                f"DARRYL_LOCAL_DIR does not point at a directory: {self.root_dir!r}."
            )
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            mime_type = guess_mime(path)
            if mime_type is None or not is_supported(mime_type):
                continue
            data = path.read_bytes()
            relative_parent = str(path.parent.relative_to(root))
            yield SourceDocument(
                # The relative path is the stable identity: moving a file
                # is a remove + add, which the sync handles naturally.
                origin_ref=f"local:{path.relative_to(root)}",
                title=path.name,
                mime_type=mime_type,
                folder_path="" if relative_parent == "." else relative_parent,
                modified_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                web_view_link=None,
                content_sha256=hashlib.sha256(data).hexdigest(),
                text=extract_content(mime_type, data),
            )
