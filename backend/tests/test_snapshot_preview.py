"""Snapshot preview integration tests against the isolated PostgreSQL test DB."""
from app.core.config import get_settings


def test_snapshot_requires_auth_enabled(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", False)
    response = client.get("/integration/v1/snapshot-preview")
    assert response.status_code == 503
    assert "incidents" not in response.text


def test_snapshot_rejects_missing_and_wrong_key(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_key", "snapshot-test-only-key")
    path = "/integration/v1/snapshot-preview"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-API-Key": "wrong"}).status_code == 401


def test_snapshot_returns_complete_read_only_collections(client, monkeypatch):
    settings = get_settings()
    # Seed through normal endpoints before enabling auth.
    monkeypatch.setattr(settings, "auth_enabled", False)
    incident = client.post("/incidents", json={
        "location": "Synthetic test location", "type": "flood",
        "severity": "CRITICAL", "latitude": 12.9, "longitude": 77.6,
    })
    assert incident.status_code == 201, incident.text
    incident_id = incident.json()["id"]
    resource = client.post("/resources", json={
        "type": "ambulance", "location": "Synthetic depot",
    })
    assert resource.status_code == 201, resource.text
    resource_id = resource.json()["id"]

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_key", "snapshot-test-only-key")
    response = client.get("/integration/v1/snapshot-preview",
                          headers={"X-API-Key": "snapshot-test-only-key"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == 1
    assert body["revision"] is None  # Not yet a versioned sync protocol.
    assert body["complete"] is True
    assert any(row["id"] == incident_id for row in body["incidents"])
    assert any(row["id"] == resource_id for row in body["resources"])
    for name in ("assignments", "recommendations", "reports", "activity"):
        assert isinstance(body[name], list)
    assert "snapshot-test-only-key" not in response.text
    # A GET must not mutate operational records.
    again = client.get("/integration/v1/snapshot-preview",
                       headers={"X-API-Key": "snapshot-test-only-key"})
    assert again.status_code == 200
    assert len(again.json()["incidents"]) == len(body["incidents"])


def test_snapshot_rejects_production_environment(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_key", "snapshot-test-only-key")
    response = client.get("/integration/v1/snapshot-preview",
                          headers={"X-API-Key": "snapshot-test-only-key"})
    assert response.status_code == 503
    assert "incidents" not in response.text
