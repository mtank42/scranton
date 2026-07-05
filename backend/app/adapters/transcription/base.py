"""Transcriber: the input-modality seam, so voice is never a special case.

Implementations are V2 (whisper.cpp local, Web Speech, Mistral STT) for
the async voice capture mode ('in the truck'). The seam exists from M0
because text must stay the single internal representation: audio becomes
text here, then flows through the exact same Tell Dwight pipeline.
Nothing downstream may ever care whether an input was typed or spoken.
"""

from abc import ABC, abstractmethod


class Transcriber(ABC):
    """Abstract contract: turn an audio payload into plain text."""

    @abstractmethod
    def transcribe(self, audio: bytes) -> str:
        """Return the text transcription of the given audio bytes."""
