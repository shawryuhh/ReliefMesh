"""Incident mutations advance the revision once per committed transaction."""
from app.db.session import SessionLocal
from app.services.operational_revision import current_operational_revision


def _revision():
    with SessionLocal() as db:
        return current_operational_revision(db)


def test_incident_create_update_cancel_increment_once(client):
    assert _revision() == 0
    created = client.post("/incidents", json={
        "location": "Synthetic location", "type": "flood", "severity": "HIGH",
    })
    assert created.status_code == 201, created.text
    incident_id = created.json()["id"]
    assert _revision() == 1

    updated = client.patch(f"/incidents/{incident_id}", json={"priority_score": 42})
    assert updated.status_code == 200, updated.text
    assert _revision() == 2

    cancelled = client.post(f"/incidents/{incident_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert _revision() == 3

    # Failed terminal transition rolls back without advancing revision.
    failed = client.post(f"/incidents/{incident_id}/cancel")
    assert failed.status_code in (409, 422)
    assert _revision() == 3
