def test_incident_creation_is_logged_automatically(client):
    incident_id = client.post(
        "/incidents",
        json={"location": "Test Location", "type": "flood", "severity": "HIGH"},
    ).json()["id"]

    logs = client.get("/activity-log", params={"incident_id": incident_id}).json()
    assert len(logs) == 1
    assert logs[0]["action"] == "incident_received"
    assert logs[0]["incident_id"] == incident_id


def test_create_manual_activity_log_entry(client):
    response = client.post(
        "/activity-log",
        json={
            "source": "ai",
            "action": "duplicate_merged",
            "reason": "Two WhatsApp reports described the same event",
            "metadata": {"merged_report_ids": ["wa-1", "wa-2"]},
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["action"] == "duplicate_merged"
    assert body["metadata"] == {"merged_report_ids": ["wa-1", "wa-2"]}

    fetched = client.get(f"/activity-log/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_manual_activity_log_rejects_unknown_incident_reference(client):
    response = client.post(
        "/activity-log",
        json={
            "source": "ai",
            "action": "duplicate_merged",
            "incident_id": "INC-does-not-exist",
        },
    )
    assert response.status_code == 422


def test_activity_log_has_no_mutation_endpoints(client):
    log_id = client.post(
        "/activity-log", json={"source": "ai", "action": "duplicate_merged"}
    ).json()["id"]

    assert client.patch(f"/activity-log/{log_id}", json={"action": "changed"}).status_code == 405
    assert client.put(f"/activity-log/{log_id}", json={"action": "changed"}).status_code == 405
    assert client.delete(f"/activity-log/{log_id}").status_code == 405


def test_activity_log_filters_by_source_and_action(client):
    client.post("/activity-log", json={"source": "ai", "action": "duplicate_merged"})
    client.post("/activity-log", json={"source": "n8n", "action": "road_blocked"})

    filtered = client.get(
        "/activity-log", params={"source": "n8n", "action": "road_blocked"}
    ).json()
    assert len(filtered) == 1
    assert filtered[0]["source"] == "n8n"


def test_get_unknown_activity_log_entry_returns_404(client):
    response = client.get("/activity-log/999999")
    assert response.status_code == 404


# Mirrors one replacement approval: several events, one transaction, so they
# all share a single now() timestamp and only their ids tell them apart.
SAME_TRANSACTION_ACTIONS = [
    "replacement_approved", "assignment_superseded", "resource_dispatched",
    "resource_dispatched", "assignment_superseded", "redispatched",
]


def _log_events_in_one_transaction(incident_id):
    from app.db.session import SessionLocal
    from app.services.action_log_service import record_action

    with SessionLocal() as db:
        ids = [
            record_action(db, source="coordinator", action=action, incident_id=incident_id).id
            for action in SAME_TRANSACTION_ACTIONS
        ]
        db.commit()
    return ids


def _create_incident(client):
    return client.post(
        "/incidents", json={"location": "Test Location", "type": "flood", "severity": "HIGH"}
    ).json()["id"]


def test_same_transaction_events_are_listed_in_insertion_order(client):
    incident_id = _create_incident(client)
    ids = _log_events_in_one_transaction(incident_id)

    logs = [
        log
        for log in client.get("/activity-log", params={"incident_id": incident_id}).json()
        if log["id"] in ids
    ]
    # The tie is real: every event has the same timestamp.
    assert len({log["timestamp"] for log in logs}) == 1
    # Newest first, i.e. exact reverse insertion order — decided by id.
    assert [log["id"] for log in logs] == sorted(ids, reverse=True)
    assert [log["action"] for log in logs] == list(reversed(SAME_TRANSACTION_ACTIONS))


def test_dashboard_orders_tied_timestamps_by_id_not_storage_order(client):
    """The dashboard's unfiltered query can be served by scanning the
    timestamp index, which returns tied rows in on-disk order. That only
    matches id order by coincidence, so store them in the opposite order
    (ids drawn up front, written highest first) to prove id decides."""
    from sqlalchemy import text

    from app.db.session import SessionLocal
    from app.models.action_log import ActionLog

    with SessionLocal() as db:
        ids = [
            db.execute(text("SELECT nextval('action_logs_id_seq')")).scalar_one()
            for _ in SAME_TRANSACTION_ACTIONS
        ]
        for log_id, action in reversed(list(zip(ids, SAME_TRANSACTION_ACTIONS))):
            db.add(ActionLog(id=log_id, source="coordinator", action=action))
            db.flush()
        db.commit()

    recent = client.get("/dashboard").json()["recent_activity"]
    assert len({log["timestamp"] for log in recent}) == 1
    assert [log["id"] for log in recent] == sorted(ids, reverse=True)
    assert [log["action"] for log in recent] == list(reversed(SAME_TRANSACTION_ACTIONS))
