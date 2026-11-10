def test_dashboard_aggregates_incidents_resources_and_activity(client):
    from app.db.session import SessionLocal
    from app.models.recommendation import Recommendation
    from app.services.id_generator import next_recommendation_id

    incident_id = client.post(
        "/incidents",
        json={"location": "Krishna Apartments", "type": "flood", "severity": "CRITICAL"},
    ).json()["id"]
    resource_id = client.post(
        "/resources", json={"type": "ambulance", "location": "Depot 1"}
    ).json()["id"]

    with SessionLocal() as db:
        rec_id = next_recommendation_id(db)
        db.add(Recommendation(
            id=rec_id, incident_id=incident_id, version=1,
            recommended_resources=[resource_id], reason="plan.reason",
            state="approved", decided_by="coordinator",
        ))
        db.commit()

    client.post(
        "/assignments",
        json={
            "incident_id": incident_id, "resource_ids": [resource_id],
            "recommendation_id": rec_id, "decision_source": "ai",
        },
    )

    response = client.get("/dashboard")
    assert response.status_code == 200
    body = response.json()

    assert body["incident_counts"]["by_status"]["ASSIGNED"] == 1
    assert body["incident_counts"]["by_severity"]["CRITICAL"] == 1
    assert body["incident_counts"]["critical_count"] == 1
    assert body["incident_counts"]["high_priority_count"] == 1

    assert body["resource_counts"]["by_status"]["DISPATCHED"] == 1
    assert body["resource_counts"]["by_type"]["ambulance"] == 1
    assert body["resource_counts"]["available_count"] == 0

    assert body["active_assignments_count"] == 1
    assert any(entry["incident_id"] == incident_id for entry in body["recent_activity"])
    assert any(incident["id"] == incident_id for incident in body["current_incidents"])
    assert any(resource["id"] == resource_id for resource in body["current_resources"])


def test_dashboard_excludes_resolved_incidents_from_current_and_high_priority(client):
    incident_id = client.post(
        "/incidents",
        json={"location": "Elsewhere", "type": "medical", "severity": "CRITICAL"},
    ).json()["id"]
    client.post(f"/incidents/{incident_id}/cancel")

    body = client.get("/dashboard").json()

    assert body["incident_counts"]["critical_count"] == 0
    assert body["incident_counts"]["high_priority_count"] == 0
    assert not any(incident["id"] == incident_id for incident in body["current_incidents"])
    # Still counted in the overall status breakdown, just not as "current".
    assert body["incident_counts"]["by_status"]["CANCELLED"] == 1


def test_dashboard_activity_limit_is_respected(client):
    for i in range(5):
        client.post("/activity-log", json={"source": "ai", "action": f"event_{i}"})

    body = client.get("/dashboard", params={"activity_limit": 2}).json()
    assert len(body["recent_activity"]) == 2
