"""IngestionSource: the connector seam for every raw data source.

This is a connector registry in the making: LocalSource (MVP), Google
Drive (MLP), then WhatsApp exports, Apple Notes, email, Dropbox, SME
systems. Every source normalizes its content into RawDoc at the edge,
so the Tell Dwight pipeline never knows where a document came from.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable

from backend.app.domain.schemas import RawDoc


class IngestionSource(ABC):
    """Abstract contract: fetch raw material, yield normalized RawDoc units."""

    @abstractmethod
    def fetch(self) -> Iterable[RawDoc]:
        """Yield every available document from the source as a RawDoc."""
