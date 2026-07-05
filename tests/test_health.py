"""The /api/v1/health endpoint: first route, first test."""


def test_health_returns_ok(client):
    """A healthy app answers 200 with the documented payload."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
