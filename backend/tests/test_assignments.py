import threading
from concurrent.futures import ThreadPoolExecutor

from app.db.session import SessionLocal
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus
from app.models.recommendation import Recommendation
from app.services.id_generator import next_recommendation_id


def _create_incident(client, location="Test Location", severity="HIGH"):
    response = client.post(
        "/incidents",
        json={"location": location, "type": "flood", "severity": severity},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_resource(client, resource_type="ambulance", location="Depot"):
    response = client.post("/resources", json={"type": resource_type, "location": location})
    assert response.status_code == 201
    return response.json()["id"]


def _approved_recommendation(incident_id, resource_ids, version=1, decided_by="coordinator"):
    """Phase 4: POST /assignments requires an APPROVED recommendation that's
    current for the incident and covers every requested resource — this
    writes one directly (bypassing the approve endpoint, which would also
    dispatch the resources itself) so these tests can exercise assignment
    creation/lifecycle on its own, the same way earlier phases wrote
    Recommendation rows directly via SessionLocal."""
    with SessionLocal() as db:
        rec_id = next_recommendation_id(db)
        db.add(Recommendation(
            id=rec_id, incident_id=incident_id, version=version,
            recommended_resources=resource_ids, reason="plan.reason",
            state="approved", decided_by=decided_by,
        ))
        db.commit()
    return rec_id


def _assign(client, incident_id, resource_ids, **overrides):
    recommendation_id = overrides.pop("recommendation_id", None) or _approved_recommendation(
        incident_id, resource_ids
    )
    payload = {
        "incident_id": incident_id,
        "resource_ids": resource_ids,
        "recommendation_id": recommendation_id,
        "decision_source": "ai",
        **overrides,
    }
    return client.post("/assignments", json=payload)


def test_create_assignment_updates_incident_and_resource(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)

    response = _assign(client, incident_id, [resource_id], reason="Medical emergency")
    assert response.status_code == 201
    assignments = response.json()
    assert len(assignments) == 1
    assert assignments[0]["status"] == "ASSIGNED"
    assert assignments[0]["resource_id"] == resource_id
    assert assignments[0]["incident_id"] == incident_id
    # approved_by comes from the recommendation's decided_by, not the request.
    assert assignments[0]["approved_by"] == "coordinator"

    incident = client.get(f"/incidents/{incident_id}").json()
    assert incident["status"] == "ASSIGNED"
    assert len(incident["current_assignments"]) == 1

    resource = client.get(f"/resources/{resource_id}").json()
    assert resource["status"] == "DISPATCHED"


def test_create_assignment_with_ai_recommendation_logs_it(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    recommendation_id = _approved_recommendation(incident_id, [resource_id])

    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id,
            "resource_ids": [resource_id],
            "recommendation_id": recommendation_id,
            "decision_source": "ai",
            "ai_recommendation": {
                "incident_id": incident_id,
                "priority_score": 94,
                "recommended_resources": [resource_id],
                "reason": "Medical emergency involving a vulnerable person",
            },
        },
    )
    assert response.status_code == 201


def test_direct_assignment_without_recommendation_is_rejected(client):
    """The bypass this phase closes: no recommendation_id at all."""
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)

    response = client.post(
        "/assignments",
        json={"incident_id": incident_id, "resource_ids": [resource_id], "decision_source": "ai"},
    )
    assert response.status_code == 422


def test_direct_assignment_with_pending_recommendation_is_rejected(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    with SessionLocal() as db:
        rec_id = next_recommendation_id(db)
        db.add(Recommendation(
            id=rec_id, incident_id=incident_id, version=1,
            recommended_resources=[resource_id], reason="plan.reason",
        ))
        db.commit()

    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id, "resource_ids": [resource_id],
            "recommendation_id": rec_id, "decision_source": "ai",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "APPROVAL_REQUIRED"
    assert client.get(f"/resources/{resource_id}").json()["status"] == "AVAILABLE"


def test_direct_assignment_with_rejected_recommendation_is_rejected(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    with SessionLocal() as db:
        rec_id = next_recommendation_id(db)
        db.add(Recommendation(
            id=rec_id, incident_id=incident_id, version=1,
            recommended_resources=[resource_id], reason="plan.reason", state="rejected",
        ))
        db.commit()

    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id, "resource_ids": [resource_id],
            "recommendation_id": rec_id, "decision_source": "ai",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "APPROVAL_REQUIRED"


def test_direct_assignment_with_approved_recommendation_succeeds(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    rec_id = _approved_recommendation(incident_id, [resource_id])

    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id, "resource_ids": [resource_id],
            "recommendation_id": rec_id, "decision_source": "ai",
        },
    )
    assert response.status_code == 201
    assert response.json()[0]["recommendation_id"] == rec_id


def test_recommendation_belonging_to_another_incident_is_rejected(client):
    incident_id = _create_incident(client, "Location A")
    other_incident_id = _create_incident(client, "Location B")
    resource_id = _create_resource(client)
    rec_id = _approved_recommendation(other_incident_id, [resource_id])

    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id, "resource_ids": [resource_id],
            "recommendation_id": rec_id, "decision_source": "ai",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "APPROVAL_REQUIRED"


def test_resource_not_part_of_approved_recommendation_is_rejected(client):
    incident_id = _create_incident(client)
    approved_resource = _create_resource(client)
    other_resource = _create_resource(client)
    rec_id = _approved_recommendation(incident_id, [approved_resource])

    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id, "resource_ids": [other_resource],
            "recommendation_id": rec_id, "decision_source": "ai",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "APPROVAL_REQUIRED"
    assert client.get(f"/resources/{other_resource}").json()["status"] == "AVAILABLE"


def test_stale_recommendation_cannot_dispatch_once_a_newer_version_exists(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    rec_id = _approved_recommendation(incident_id, [resource_id], version=1)
    # A newer version supersedes it as "current" even though v1 is APPROVED.
    _approved_recommendation(incident_id, [resource_id], version=2)

    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id, "resource_ids": [resource_id],
            "recommendation_id": rec_id, "decision_source": "ai",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "STALE_PLAN"


def test_reassigning_already_live_pair_is_idempotent(client):
    """Calling /assignments again for a resource already live-assigned to
    the same incident (e.g. already dispatched by approval) returns the
    existing assignment rather than erroring or duplicating it."""
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    rec_id = _approved_recommendation(incident_id, [resource_id])

    first = client.post(
        "/assignments",
        json={
            "incident_id": incident_id, "resource_ids": [resource_id],
            "recommendation_id": rec_id, "decision_source": "ai",
        },
    )
    assert first.status_code == 201
    first_id = first.json()[0]["id"]

    second = client.post(
        "/assignments",
        json={
            "incident_id": incident_id, "resource_ids": [resource_id],
            "recommendation_id": rec_id, "decision_source": "ai",
        },
    )
    assert second.status_code == 201
    assert second.json()[0]["id"] == first_id

    with SessionLocal() as db:
        live = (
            db.query(Assignment)
            .filter(
                Assignment.resource_id == resource_id,
                Assignment.status.in_((AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)),
            )
            .all()
        )
    assert len(live) == 1


def test_cannot_assign_already_dispatched_resource(client):
    incident_a = _create_incident(client, "Location A")
    incident_b = _create_incident(client, "Location B")
    resource_id = _create_resource(client)

    first = _assign(client, incident_a, [resource_id])
    assert first.status_code == 201

    second = _assign(client, incident_b, [resource_id])
    assert second.status_code == 409
    assert second.json()["code"] == "RESOURCE_UNAVAILABLE"


def test_create_assignment_unknown_incident_returns_404(client):
    resource_id = _create_resource(client)
    response = client.post(
        "/assignments",
        json={
            "incident_id": "INC-does-not-exist",
            "resource_ids": [resource_id],
            "recommendation_id": "REC-does-not-exist",
            "decision_source": "ai",
        },
    )
    assert response.status_code == 404


def test_create_assignment_unknown_resource_returns_404(client):
    incident_id = _create_incident(client)
    rec_id = _approved_recommendation(incident_id, ["AMB-does-not-exist"])
    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id,
            "resource_ids": ["AMB-does-not-exist"],
            "recommendation_id": rec_id,
            "decision_source": "ai",
        },
    )
    assert response.status_code == 404


def test_create_assignment_is_all_or_nothing(client):
    incident_id = _create_incident(client)
    available_resource = _create_resource(client)
    already_taken_resource = _create_resource(client)

    other_incident = _create_incident(client, "Elsewhere")
    _assign(client, other_incident, [already_taken_resource])

    rec_id = _approved_recommendation(incident_id, [available_resource, already_taken_resource])
    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id,
            "resource_ids": [available_resource, already_taken_resource],
            "recommendation_id": rec_id,
            "decision_source": "ai",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "RESOURCE_UNAVAILABLE"

    # The available resource must NOT have been dispatched by the failed
    # all-or-nothing attempt.
    resource = client.get(f"/resources/{available_resource}").json()
    assert resource["status"] == "AVAILABLE"


def test_assignment_lifecycle_activate_then_complete_frees_resource(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)

    assignment_id = _assign(client, incident_id, [resource_id]).json()[0]["id"]

    activate = client.post(f"/assignments/{assignment_id}/status", json={"status": "ACTIVE"})
    assert activate.status_code == 200
    assert activate.json()["status"] == "ACTIVE"
    assert client.get(f"/resources/{resource_id}").json()["status"] == "ACTIVE"

    complete = client.post(f"/assignments/{assignment_id}/status", json={"status": "COMPLETED"})
    assert complete.status_code == 200
    assert complete.json()["status"] == "COMPLETED"
    assert complete.json()["completed_at"] is not None
    assert client.get(f"/resources/{resource_id}").json()["status"] == "AVAILABLE"


def test_cancel_assignment_frees_resource(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    assignment_id = _assign(client, incident_id, [resource_id]).json()[0]["id"]

    cancel = client.post(
        f"/assignments/{assignment_id}/status",
        json={"status": "CANCELLED", "reason": "false alarm"},
    )
    assert cancel.status_code == 200
    assert client.get(f"/resources/{resource_id}").json()["status"] == "AVAILABLE"


def test_invalid_assignment_transition_is_rejected(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    assignment_id = _assign(client, incident_id, [resource_id]).json()[0]["id"]

    # ASSIGNED -> COMPLETED is not a direct transition (must go through ACTIVE).
    response = client.post(f"/assignments/{assignment_id}/status", json={"status": "COMPLETED"})
    assert response.status_code == 409


def test_superseded_is_rejected_via_status_endpoint(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    assignment_id = _assign(client, incident_id, [resource_id]).json()[0]["id"]

    response = client.post(f"/assignments/{assignment_id}/status", json={"status": "SUPERSEDED"})
    assert response.status_code == 422


def test_concurrent_assignment_of_same_resource_is_serialized_not_double_booked(client):
    """Two requests race to assign the same AVAILABLE resource to two
    different incidents, each backed by its own approved recommendation.
    Real PostgreSQL row locking (SELECT ... FOR UPDATE) must serialize them
    so exactly one succeeds; the partial unique index is the backstop if it
    didn't."""
    incident_a = _create_incident(client, "Location A")
    incident_b = _create_incident(client, "Location B")
    resource_id = _create_resource(client)
    rec_a = _approved_recommendation(incident_a, [resource_id])
    rec_b = _approved_recommendation(incident_b, [resource_id])

    barrier = threading.Barrier(2)
    results: dict[str, object] = {}

    def attempt(name: str, incident_id: str, recommendation_id: str) -> None:
        barrier.wait()
        results[name] = client.post(
            "/assignments",
            json={
                "incident_id": incident_id,
                "resource_ids": [resource_id],
                "recommendation_id": recommendation_id,
                "decision_source": "ai",
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attempt, "a", incident_a, rec_a),
            executor.submit(attempt, "b", incident_b, rec_b),
        ]
        for future in futures:
            future.result()

    status_codes = sorted(r.status_code for r in results.values())
    assert status_codes == [201, 409]

    resource = client.get(f"/resources/{resource_id}").json()
    assert resource["status"] == "DISPATCHED"

    with SessionLocal() as db:
        live_assignments = (
            db.query(Assignment)
            .filter(
                Assignment.resource_id == resource_id,
                Assignment.status.in_((AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)),
            )
            .all()
        )
    assert len(live_assignments) == 1
