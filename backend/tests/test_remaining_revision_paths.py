"""Regression tests for revision updates on remaining write paths."""
from app.db.session import SessionLocal
from app.services.operational_revision import current_operational_revision


def revision():
    with SessionLocal() as db:
        return current_operational_revision(db)


def test_manual_activity_log_increments_revision_once(client):
    assert revision() == 0
    response = client.post("/activity-log", json={
        "source": "system", "action": "synthetic_revision_test",
    })
    assert response.status_code in (200, 201), response.text
    assert revision() == 1


def test_recommendation_proposal_increments_revision_without_dispatch(client):
    incident = client.post("/incidents", json={
        "location": "Synthetic test site", "type": "flood", "severity": "HIGH",
    })
    assert incident.status_code == 201, incident.text
    incident_id = incident.json()["id"]
    resource = client.post("/resources", json={
        "type": "ambulance", "location": "Synthetic depot",
    })
    assert resource.status_code == 201, resource.text
    resource_id = resource.json()["id"]
    before = revision()
    response = client.post(f"/integration/v1/incidents/{incident_id}/recommendation", json={
        "recommended_resources": [resource_id],
        "reason": "plan.reason", "explanation": [],
        "confidence": 0.9, "priority_score": 75,
        "analysis_revision": "revision-test-1",
    })
    assert response.status_code == 201, response.text
    assert revision() == before + 1
    assignments = client.get("/assignments", params={"incident_id": incident_id})
    assert assignments.status_code == 200
    assert assignments.json() == []
