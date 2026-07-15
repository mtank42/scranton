"""Character configuration map: the agent registry and IP-safe rebrand seam.

Each entry is one of Scranton's specialized agents (Dwight structures,
Pam remembers, Toby aggregates, ...) - narrow mandate, shared memory,
orchestrated by the manager (SCRANTON_CONTEXT.md section 1).

Every display name and avatar in the product comes from this map. Routes
and UI reference character keys only ('dwight', 'pam', ...), never the
names or the filenames. The whole brand currently leans on The Office IP
(PRODUCT_ROADMAP.md section 8): if a clean-room rebrand is ever needed,
it happens here in one file - a config change, not a refactor.
"""

from typing import TypedDict


class Character(TypedDict):
    """One product character: how a feature presents itself to the user."""

    display_name: str
    avatar_asset: str


CHARACTERS: dict[str, Character] = {
    "dwight": {
        "display_name": "Tell Dwight",
        "avatar_asset": "dwight-removebg-preview.png",
    },
    "pam": {
        "display_name": "Ask Pam",
        "avatar_asset": "pam-removebg-preview.png",
    },
    "jim": {
        "display_name": "Whisper Jim",
        "avatar_asset": "jim-removebg-preview.png",
    },
    "michael": {
        "display_name": "Michael's Desk",
        "avatar_asset": "michael-removebg-preview.png",
    },
    "angela": {
        "display_name": "Send Angela",
        "avatar_asset": "angela-removebg-preview.png",
    },
    "toby": {
        "display_name": "Meet Toby",
        "avatar_asset": "toby-removebg-preview.png",
    },
    # The invisible archivist (session 2026-07-15): no view of his own,
    # surfaced through the Pam overlay strip. No avatar yet - the strip
    # does not render one; the asset joins when the owner provides it.
    "darryl": {
        "display_name": "Darryl",
        "avatar_asset": "",
    },
}
