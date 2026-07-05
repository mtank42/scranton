"""Application settings loaded from the environment.

Why a dedicated module: everything physical (provider choice, API keys,
data locations) must come from configuration, never from code. This is a
core seam of the architecture (ARCHITECTURE_SKETCH.md section 13): the
same build must run on a local disk, a NAS mount, or a cloud volume with
nothing but a different environment.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load the git-ignored .env once at import time. override=False means a
# variable already set in the real environment wins over the file, so a
# deployment can override local defaults without editing anything.
load_dotenv(override=False)

# Repository root, derived from this file's location:
# backend/app/config.py -> backend/app -> backend -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of the application configuration.

    Frozen on purpose: a Settings object can never drift after creation,
    so tests and services always reason about one consistent set of values.
    """

    llm_provider: str
    mistral_api_key: str
    gemini_api_key: str
    database_url: str
    chroma_dir: str


def get_settings() -> Settings:
    """Build a Settings snapshot from the current environment.

    Reading the environment here (and not at module import) lets tests
    override variables with monkeypatch and get fresh values on the next
    call: no global mutable state to reset between tests.
    """
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "mistral"),
        mistral_api_key=os.getenv("MISTRAL_API_KEY", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        database_url=os.getenv(
            "DATABASE_URL", f"sqlite:///{REPO_ROOT / 'data' / 'scranton.db'}"
        ),
        chroma_dir=os.getenv("CHROMA_DIR", str(REPO_ROOT / "data" / "chroma")),
    )
