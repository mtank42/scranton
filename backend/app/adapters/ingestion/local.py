"""Local source (MVP): the owner's local files and manual test material."""

from collections.abc import Iterable

from backend.app.adapters.ingestion.base import IngestionSource
from backend.app.domain.schemas import RawDoc


class LocalSource(IngestionSource):
    """Reads documents from a local folder. Lands with Tell Dwight (M1).

    Manual capture through the Tell Dwight endpoint does not go through
    this class: an ingestion source is for pulling existing documents in
    bulk, not for interactive input.
    """

    def fetch(self) -> Iterable[RawDoc]:
        """Not implemented yet: M1 wires local files into the pipeline."""
        raise NotImplementedError("LocalSource.fetch lands in M1 (Tell Dwight).")
