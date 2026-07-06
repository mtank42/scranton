"""The UI shell: static serving and the config endpoint."""


def test_root_serves_the_app_shell(client):
    """GET / returns the single-page shell."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Scranton" in response.text
    assert "app.js" in response.text


def test_ui_config_exposes_the_character_map(client):
    """The frontend gets names and avatars from the seam, not hardcoded."""
    response = client.get("/api/v1/config/ui")
    assert response.status_code == 200
    characters = response.json()["characters"]
    assert set(characters) == {"dwight", "pam", "jim", "michael", "angela", "toby"}
    assert characters["dwight"]["display_name"] == "Tell Dwight"
    assert characters["dwight"]["avatar_asset"].endswith(".png")


def test_avatar_assets_are_served(client):
    """The avatar files referenced by the map exist under /assets."""
    config = client.get("/api/v1/config/ui").json()
    for character in config["characters"].values():
        response = client.get(f"/assets/{character['avatar_asset']}")
        assert response.status_code == 200, character