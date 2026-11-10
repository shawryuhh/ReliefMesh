def test_create_and_get_resource(client):
    create_response = client.post(
        "/resources",
        json={
            "type": "ambulance",
            "location": "Sector 12 Depot",
            "capabilities": ["medical"],
            "capacity": 2,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"].startswith("AMB-")
    assert created["status"] == "AVAILABLE"

    get_response = client.get(f"/resources/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]


def test_get_unknown_resource_returns_404(client):
    response = client.get("/resources/AMB-does-not-exist")
    assert response.status_code == 404


def test_list_resources_filters_by_type_and_status(client):
    create_response = client.post(
        "/resources",
        json={"type": "rescue_unit", "location": "Central Depot"},
    )
    resource_id = create_response.json()["id"]

    list_response = client.get(
        "/resources", params={"type": "rescue_unit", "status": "AVAILABLE"}
    )
    assert list_response.status_code == 200
    ids = [resource["id"] for resource in list_response.json()]
    assert resource_id in ids


def test_update_resource_status_valid_transition(client):
    create_response = client.post(
        "/resources",
        json={"type": "ambulance", "location": "Sector 12 Depot"},
    )
    resource_id = create_response.json()["id"]

    status_response = client.post(
        f"/resources/{resource_id}/status",
        json={"resource_id": resource_id, "status": "DISPATCHED", "reason": "en route"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "DISPATCHED"


def test_update_resource_status_invalid_transition_is_rejected(client):
    create_response = client.post(
        "/resources",
        json={"type": "ambulance", "location": "Sector 12 Depot"},
    )
    resource_id = create_response.json()["id"]

    # AVAILABLE -> ACTIVE is not an allowed direct transition.
    response = client.post(
        f"/resources/{resource_id}/status",
        json={"resource_id": resource_id, "status": "ACTIVE"},
    )
    assert response.status_code == 409


def test_update_resource_status_mismatched_body_id_is_rejected(client):
    create_response = client.post(
        "/resources",
        json={"type": "ambulance", "location": "Sector 12 Depot"},
    )
    resource_id = create_response.json()["id"]

    response = client.post(
        f"/resources/{resource_id}/status",
        json={"resource_id": "AMB-mismatch", "status": "DISPATCHED"},
    )
    assert response.status_code == 422
