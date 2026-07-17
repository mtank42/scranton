"""The character map: the single source for display names and avatars."""

from backend.app.domain.characters import CHARACTERS

POC_CHARACTERS = {"dwight", "pam", "jim", "michael", "angela", "toby", "darryl"}


def test_the_poc_characters_are_registered():
    """Every character key the POC can reference exists in the map."""
    assert set(CHARACTERS) == POC_CHARACTERS


def test_every_character_is_fully_described():
    """Each entry carries a display name and an avatar asset.

    A missing value here would push whoever builds the UI to hardcode a
    name or a filename, which is exactly what this seam forbids. Darryl
    is the exception that proves the seam: the invisible archivist has
    no avatar surface yet, so his asset stays empty until the owner
    provides one.
    """
    for key, character in CHARACTERS.items():
        assert character["display_name"], key
        # The person behind the action (owner, QA v6): sentences say
        # 'Dwight', buttons and tabs say 'Tell Dwight'.
        assert character["agent_name"], key
        assert "Tell" not in character["agent_name"]
        assert "Ask" not in character["agent_name"]
        if key != "darryl":
            assert character["avatar_asset"].endswith(".png"), key
