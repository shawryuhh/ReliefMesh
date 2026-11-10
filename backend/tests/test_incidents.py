def test_create_and_get_incident(client):
    create_response = client.post(
        "/incidents",
        json={
            "location": "Krishna Apartments, Block C",
            "type": "flood",
            "severity": "CRITICAL",
            "people_affected": 4,
            "needs": ["medical", "evacuation"],
            "report_metadata": {"channel": "whatsapp"},
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"].startswith("INC-")
    assert created["status"] == "UNASSIGNED"
    assert created["current_assignments"] == []

    get_response = client.get(f"/incidents/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]


def test_get_unknown_incident_returns_404(client):
    response = client.get("/incidents/INC-does-not-exist")
    assert response.status_code == 404


def test_list_incidents_filters_by_status(client):
    create_response = client.post(
        "/incidents",
        json={
            "location": "Test Location",
            "type": "medical",
            "severity": "LOW",
        },
    )
    incident_id = create_response.json()["id"]

    list_response = client.get("/incidents", params={"status": "UNASSIGNED"})
    assert list_response.status_code == 200
    ids = [incident["id"] for incident in list_response.json()]
    assert incident_id in ids


def test_cancel_incident_transitions_status(client):
    create_response = client.post(
        "/incidents",
        json={
            "location": "Test Location",
            "type": "other",
            "severity": "LOW",
        },
    )
    incident_id = create_response.json()["id"]

    cancel_response = client.post(
        f"/incidents/{incident_id}/cancel", json={"reason": "false alarm"}
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELLED"

    # Cancelling again is not a valid transition.
    repeat_response = client.post(f"/incidents/{incident_id}/cancel")
    assert repeat_response.status_code == 409
