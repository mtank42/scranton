"""UI configuration endpoint.

The frontend fetches display names and avatar assets from here instead
of hardcoding them: the character map stays the single seam for the
IP-safe rebrand (PRODUCT_ROADMAP.md section 8).
"""

from fastapi import APIRouter

from backend.app.domain.characters import CHARACTERS, Character

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/ui")
def get_ui_config() -> dict[str, dict[str, Character]]:
    """Return the character map (display names + avatar assets)."""
    return {"characters": CHARACTERS}
