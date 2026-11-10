"""Phase 3: recommendation approval — the human approval gate.

Approval has its own atomic transaction (recommendation_service.approve_
recommendation): approve the PENDING recommendation, dispatch its resources,
create the assignments, all-or-nothing. These tests exercise that directly
through the HTTP API, the same way test_assignments.py does for assignments.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus, OperationalPhase
from app.models.incident import Incident
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


def _create_pending_recommendation(incident_id, resource_ids, version=1, **overrides):
    fields = {
        "reason": "plan.reason",
        "confidence": 0.91,
        "priority_score": 94,
        **overrides,
    }
    with SessionLocal() as db:
        rec_id = next_recommendation_id(db)
        rec = Recommendation(
            id=rec_id,
            incident_id=incident_id,
            version=version,
            recommended_resources=resource_ids,
            **fields,
        )
        db.add(rec)
        # Approval is phase-gated, so put the incident where the intake/
        # proposal endpoints would have left it.
        incident = db.get(Incident, incident_id)
        incident.operational_phase = (
            OperationalPhase.AWAITING_REPLACEMENT
            if fields.get("replacement_for_resource_id")
            else OperationalPhase.AWAITING_APPROVAL
        )
        db.commit()
    return rec_id


@pytest.fixture
def auth_settings():
    """Overrides get_settings for the duration of a test so the two-key
    (coordinator/automation) model can be exercised without touching real
    env vars or the module-level cached Settings other tests rely on."""

    def _apply(**overrides):
        base = get_settings().model_dump()
        base.update(overrides)
        app.dependency_overrides[get_settings] = lambda: Settings(**base)

    yield _apply
    app.dependency_overrides.pop(get_settings, None)


def test_approve_recommendation_succeeds(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    _create_pending_recommendation(incident_id, [resource_id])

    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "approved"
    assert body["decided_by"] == "coordinator"
    assert body["decided_at"] is not None


def test_approval_creates_expected_assignments(client):
    incident_id = _create_incident(client)
    r1 = _create_resource(client, "ambulance")
    r2 = _create_resource(client, "rescue")
    _create_pending_recommendation(incident_id, [r1, r2])

    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert response.status_code == 200
    rec_id = response.json()["id"]

    assignments = client.get("/assignments", params={"incident_id": incident_id}).json()
    assert {a["resource_id"] for a in assignments} == {r1, r2}
    for assignment in assignments:
        assert assignment["status"] == "ASSIGNED"
        assert assignment["decision_source"] == "coordinator_approval"
        assert assignment["approved_by"] == "coordinator"

    with SessionLocal() as db:
        for assignment in assignments:
            row = db.get(Assignment, assignment["id"])
            assert row.recommendation_id == rec_id

    incident = client.get(f"/incidents/{incident_id}").json()
    assert incident["status"] == "ASSIGNED"

    for resource_id in (r1, r2):
        assert client.get(f"/resources/{resource_id}").json()["status"] == "DISPATCHED"


def test_approved_by_is_server_derived_not_client_supplied(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    _create_pending_recommendation(incident_id, [resource_id])

    # RecommendationApprove has no approved_by field at all — a client
    # cannot influence who the recommendation/assignments are attributed to.
    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert response.status_code == 200
    assert response.json()["decided_by"] == "coordinator"


def test_request_cannot_spoof_approved_by_in_body(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    _create_pending_recommendation(incident_id, [resource_id])

    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve",
        json={"version": 1, "approved_by": "attacker"},
    )
    assert response.status_code == 422

    # And nothing was approved as a side effect of the rejected request.
    current = client.get(f"/integration/v1/incidents/{incident_id}/recommendation").json()
    assert current["state"] == "pending"


def test_rejected_recommendation_cannot_be_approved(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    rec_id = _create_pending_recommendation(incident_id, [resource_id])
    with SessionLocal() as db:
        rec = db.get(Recommendation, rec_id)
        rec.state = "rejected"
        db.commit()

    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "STALE_PLAN"


def test_already_approved_recommendation_cannot_be_approved_again(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    _create_pending_recommendation(incident_id, [resource_id])

    first = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert first.status_code == 200

    second = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert second.status_code == 409
    assert second.json()["code"] == "STALE_PLAN"


def test_stale_version_is_rejected(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    _create_pending_recommendation(incident_id, [resource_id], version=1)

    # Approving the version that's actually current fails because the
    # caller asked for a version (2) that doesn't match what's pending (1).
    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 2}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "STALE_PLAN"

    current = client.get(f"/integration/v1/incidents/{incident_id}/recommendation").json()
    assert current["state"] == "pending"


def test_unavailable_resource_causes_complete_rollback(client):
    incident_id = _create_incident(client)
    available_resource = _create_resource(client, "ambulance")
    taken_resource = _create_resource(client, "rescue")

    # Take the second resource with an unrelated, ordinary assignment first.
    other_incident = _create_incident(client, "Elsewhere")
    other_rec_id = _create_pending_recommendation(other_incident, [taken_resource])
    with SessionLocal() as db:
        other_rec = db.get(Recommendation, other_rec_id)
        other_rec.state = "approved"
        other_rec.decided_by = "coordinator"
        db.commit()
    taken = client.post(
        "/assignments",
        json={
            "incident_id": other_incident, "resource_ids": [taken_resource],
            "recommendation_id": other_rec_id, "decision_source": "ai",
        },
    )
    assert taken.status_code == 201

    _create_pending_recommendation(incident_id, [available_resource, taken_resource])

    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "RESOURCE_UNAVAILABLE"

    # Recommendation remains PENDING.
    current = client.get(f"/integration/v1/incidents/{incident_id}/recommendation").json()
    assert current["state"] == "pending"

    # The available resource must NOT have been dispatched by the failed
    # all-or-nothing approval.
    assert client.get(f"/resources/{available_resource}").json()["status"] == "AVAILABLE"

    # No assignment was created for the available resource either.
    assignments = client.get("/assignments", params={"incident_id": incident_id}).json()
    assert assignments == []

    # The target incident's state is unchanged (still UNASSIGNED).
    assert client.get(f"/incidents/{incident_id}").json()["status"] == "UNASSIGNED"


def test_concurrent_approval_of_same_recommendation_cannot_double_book(client):
    """Two requests race to approve the same pending recommendation. Real
    PostgreSQL row locking on the recommendation row must serialize them so
    exactly one succeeds and the resource is dispatched exactly once."""
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    _create_pending_recommendation(incident_id, [resource_id])

    barrier = threading.Barrier(2)
    results: dict[str, object] = {}

    def attempt(name: str) -> None:
        barrier.wait()
        results[name] = client.post(
            f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt, "a"), executor.submit(attempt, "b")]
        for future in futures:
            future.result()

    status_codes = sorted(r.status_code for r in results.values())
    assert status_codes == [200, 409]

    assert client.get(f"/resources/{resource_id}").json()["status"] == "DISPATCHED"

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


def test_recommendation_history_is_preserved_not_overwritten(client):
    incident_id = _create_incident(client)
    r1 = _create_resource(client)
    _create_pending_recommendation(incident_id, [r1], version=1)

    approve = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert approve.status_code == 200

    # A later replacement proposal (v2) doesn't overwrite v1 — both rows exist.
    r2 = _create_resource(client)
    _create_pending_recommendation(
        incident_id, [r2], version=2, replacement_for_resource_id=r1, reason="plan.replacementReason"
    )

    with SessionLocal() as db:
        versions = {
            r.version: r.state.value
            for r in db.query(Recommendation).filter(Recommendation.incident_id == incident_id)
        }
    assert versions == {1: "approved", 2: "pending"}

    # GET .../recommendation returns the current (highest-version) one.
    current = client.get(f"/integration/v1/incidents/{incident_id}/recommendation").json()
    assert current["version"] == 2
    assert current["state"] == "pending"


def test_no_pending_recommendation_returns_404_on_get(client):
    incident_id = _create_incident(client)
    response = client.get(f"/integration/v1/incidents/{incident_id}/recommendation")
    assert response.status_code == 404


def test_approve_with_no_recommendation_returns_stale_plan_conflict(client):
    incident_id = _create_incident(client)
    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "STALE_PLAN"


def test_coordinator_key_can_approve_when_auth_enabled(client, auth_settings):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    _create_pending_recommendation(incident_id, [resource_id])

    auth_settings(auth_enabled=True, coordinator_api_key="coord-secret", automation_api_key="automation-secret")

    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve",
        json={"version": 1},
        headers={"X-API-Key": "coord-secret"},
    )
    assert response.status_code == 200
    assert response.json()["decided_by"] == "coordinator"


def test_automation_key_cannot_approve_when_auth_enabled(client, auth_settings):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    _create_pending_recommendation(incident_id, [resource_id])

    auth_settings(auth_enabled=True, coordinator_api_key="coord-secret", automation_api_key="automation-secret")

    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve",
        json={"version": 1},
        headers={"X-API-Key": "automation-secret"},
    )
    assert response.status_code == 403

    with SessionLocal() as db:
        rec = (
            db.query(Recommendation)
            .filter(Recommendation.incident_id == incident_id)
            .order_by(Recommendation.version.desc())
            .first()
        )
        assert rec.state.value == "pending"


def test_missing_key_cannot_approve_when_auth_enabled(client, auth_settings):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    _create_pending_recommendation(incident_id, [resource_id])

    auth_settings(auth_enabled=True, coordinator_api_key="coord-secret", automation_api_key="automation-secret")

    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert response.status_code == 401


def test_approval_requires_awaiting_approval_phase(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    _create_pending_recommendation(incident_id, [resource_id])
    with SessionLocal() as db:
        db.get(Incident, incident_id).operational_phase = OperationalPhase.BLOCKED
        db.commit()

    response = client.post(
        f"/integration/v1/incidents/{incident_id}/recommendation/approve", json={"version": 1}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "STALE_PLAN"
    assert client.get(f"/resources/{resource_id}").json()["status"] == "AVAILABLE"
