"""Phase 5: recommendation intake, disruption reports, and gated replacement.

The full canonical flow over HTTP — initial plan -> coordinator approval ->
road block -> replacement proposal -> coordinator approval — plus the safety
properties the old ungated /replanning endpoint used to be tested for:
all-or-nothing rollback, concurrent approvals that can't double-book, stale
versions and idempotent resubmission.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.action_log import ActionLog
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus
from app.models.recommendation import Recommendation

BASE = "/integration/v1/incidents"
LIVE = (AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)


def _create_incident(client, location="Krishna Apartments, Block C"):
    response = client.post(
        "/incidents", json={"location": location, "type": "flood", "severity": "CRITICAL"}
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_resource(client, resource_type="ambulance"):
    response = client.post("/resources", json={"type": resource_type, "location": "Depot"})
    assert response.status_code == 201
    return response.json()["id"]


def _submit_plan(client, incident_id, resources, **overrides):
    body = {"recommended_resources": resources, "reason": "plan.reason", **overrides}
    return client.post(f"{BASE}/{incident_id}/recommendation", json=body)


def _approve(client, incident_id, version):
    return client.post(f"{BASE}/{incident_id}/recommendation/approve", json={"version": version})


def _disrupt(client, incident_id, resource_id, eta=24, previous=6):
    return client.post(
        f"{BASE}/{incident_id}/disruptions",
        json={"resource_id": resource_id, "eta_minutes": eta, "previous_eta_minutes": previous},
    )


def _propose(client, incident_id, replacement_for, resources, base_version=1, **overrides):
    body = {
        "base_version": base_version,
        "replacement_for": replacement_for,
        "recommended_resources": resources,
        "reason": "plan.replacementReason",
        **overrides,
    }
    return client.post(f"{BASE}/{incident_id}/recommendation/replacement", json=body)


def _phase(client, incident_id):
    return client.get(f"/incidents/{incident_id}").json()["operational_phase"]


def _status(client, resource_id):
    return client.get(f"/resources/{resource_id}").json()["status"]


def _live_assignments(incident_id):
    with SessionLocal() as db:
        return {
            a.resource_id: a
            for a in db.query(Assignment).filter(
                Assignment.incident_id == incident_id, Assignment.status.in_(LIVE)
            )
        }


@pytest.fixture
def blocked_incident(client):
    """Krishna Apartments after AMB-02 hit a road block: v1 [amb, rescue]
    approved and dispatched, amb disrupted. Returns (incident, amb, rescue,
    spare_amb)."""
    amb = _create_resource(client, "ambulance")
    spare = _create_resource(client, "ambulance")
    rescue = _create_resource(client, "rescue_unit")
    incident_id = _create_incident(client)
    assert _submit_plan(client, incident_id, [amb, rescue]).status_code == 201
    assert _approve(client, incident_id, 1).status_code == 200
    assert _disrupt(client, incident_id, amb).status_code == 200
    return incident_id, amb, rescue, spare


@pytest.fixture
def auth_settings():
    def _apply(**overrides):
        base = get_settings().model_dump()
        base.update(overrides)
        app.dependency_overrides[get_settings] = lambda: Settings(**base)

    yield _apply
    app.dependency_overrides.pop(get_settings, None)


# --- full flow -------------------------------------------------------------


def test_full_canonical_flow_over_http(client):
    amb_02 = _create_resource(client, "ambulance")
    amb_05 = _create_resource(client, "ambulance")
    rescue_01 = _create_resource(client, "rescue_unit")
    incident_id = _create_incident(client)
    assert _phase(client, incident_id) == "received"

    # 1. AI/n8n submits the initial plan: pending, nothing dispatched.
    submitted = _submit_plan(
        client,
        incident_id,
        [amb_02, rescue_01],
        explanation=[{"key": "explain.water", "params": {"id": rescue_01}}],
        confidence=0.91,
        priority_score=94,
    )
    assert submitted.status_code == 201
    v1 = submitted.json()
    assert (v1["version"], v1["state"], v1["replacementFor"]) == (1, "pending", None)
    assert v1["explanation"] == [{"key": "explain.water", "params": {"id": rescue_01}}]
    assert _phase(client, incident_id) == "awaiting_approval"
    assert _status(client, amb_02) == "AVAILABLE"
    assert _live_assignments(incident_id) == {}

    # 2. Coordinator approves: both dispatched.
    assert _approve(client, incident_id, 1).status_code == 200
    assert _phase(client, incident_id) == "dispatched"
    initial_assignments = _live_assignments(incident_id)
    assert set(initial_assignments) == {amb_02, rescue_01}

    # 3. Road block on AMB-02: ETA revised, still dispatched.
    disrupted = _disrupt(client, incident_id, amb_02, eta=24, previous=6)
    assert disrupted.status_code == 200
    assert disrupted.json()["operational_phase"] == "blocked"
    assert _status(client, amb_02) == "DISPATCHED"
    blocked_assignment = _live_assignments(incident_id)[amb_02]
    assert (blocked_assignment.previous_eta_minutes, blocked_assignment.eta_minutes) == (6, 24)

    # 4. Replacement proposed: pending v2, nothing released or dispatched.
    proposed = _propose(client, incident_id, amb_02, [amb_05, rescue_01])
    assert proposed.status_code == 201
    v2 = proposed.json()
    assert (v2["version"], v2["state"], v2["replacementFor"]) == (2, "pending", amb_02)
    assert _phase(client, incident_id) == "awaiting_replacement"
    assert _status(client, amb_02) == "DISPATCHED"
    assert _status(client, amb_05) == "AVAILABLE"
    assert set(_live_assignments(incident_id)) == {amb_02, rescue_01}

    # 5. Coordinator approves the replacement.
    approved = _approve(client, incident_id, 2)
    assert approved.status_code == 200
    assert approved.json()["state"] == "approved"
    assert _phase(client, incident_id) == "dispatched"
    assert _status(client, amb_02) == "AVAILABLE"
    assert _status(client, amb_05) == "DISPATCHED"
    assert _status(client, rescue_01) == "DISPATCHED"

    live = _live_assignments(incident_id)
    assert set(live) == {amb_05, rescue_01}
    # RESCUE-01 continues on its original assignment, untouched.
    assert live[rescue_01].id == initial_assignments[rescue_01].id
    assert live[rescue_01].recommendation_id == v1["id"]
    assert live[amb_05].recommendation_id == v2["id"]
    assert live[amb_05].approved_by == "coordinator"

    with SessionLocal() as db:
        old = db.get(Assignment, blocked_assignment.id)
        assert old.status == AssignmentStatus.SUPERSEDED
        states = {
            r.version: r.state.value
            for r in db.query(Recommendation).filter(Recommendation.incident_id == incident_id)
        }
    assert states == {1: "approved", 2: "approved"}

    current = client.get(f"{BASE}/{incident_id}/recommendation").json()
    assert current["version"] == 2


def test_audit_trail_records_the_flow_in_order(client, blocked_incident):
    incident_id, amb, rescue, spare = blocked_incident
    assert _propose(client, incident_id, amb, [spare, rescue]).status_code == 201
    assert _approve(client, incident_id, 2).status_code == 200

    with SessionLocal() as db:
        logs = (
            db.query(ActionLog)
            .filter(ActionLog.incident_id == incident_id, ActionLog.action != "incident_received")
            .order_by(ActionLog.id)
            .all()
        )
    trail = [(log.source, log.action, log.resource_id) for log in logs]
    assert trail == [
        ("ai", "recommendation_generated", None),
        ("ai", "approval_requested", None),
        ("coordinator", "approved", None),
        ("coordinator", "resource_dispatched", amb),
        ("coordinator", "resource_dispatched", rescue),
        ("automation", "road_block_detected", amb),
        ("ai", "replanning_started", amb),
        ("ai", "replacement_recommended", None),
        ("ai", "approval_requested", None),
        ("coordinator", "replacement_approved", None),
        ("coordinator", "assignment_superseded", amb),
        ("coordinator", "resource_dispatched", spare),
        ("automation", "redispatched", None),
    ]
    road_block = next(log for log in logs if log.action == "road_block_detected")
    assert road_block.log_metadata == {"resources": amb, "old": 6, "eta": 24}
    recommended = next(log for log in logs if log.action == "replacement_recommended")
    assert recommended.log_metadata["resources"] == spare


def test_old_replanning_endpoint_is_gone(client):
    response = client.post("/replanning", json={})
    assert response.status_code == 404


# --- intake ----------------------------------------------------------------


def test_initial_submission_is_idempotent_on_analysis_revision(client):
    amb = _create_resource(client)
    incident_id = _create_incident(client)

    first = _submit_plan(client, incident_id, [amb], analysis_revision="a-1")
    replay = _submit_plan(client, incident_id, [amb], analysis_revision="a-1")
    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]

    conflicting = _submit_plan(client, incident_id, [amb, _create_resource(client)], analysis_revision="a-1")
    assert conflicting.status_code == 409
    assert conflicting.json()["code"] == "IDEMPOTENCY_CONFLICT"

    with SessionLocal() as db:
        assert db.query(Recommendation).filter(Recommendation.incident_id == incident_id).count() == 1


def test_second_initial_submission_conflicts(client):
    amb = _create_resource(client)
    incident_id = _create_incident(client)
    assert _submit_plan(client, incident_id, [amb]).status_code == 201

    pending = _submit_plan(client, incident_id, [amb])
    assert pending.status_code == 409
    assert pending.json()["code"] == "PENDING_PLAN_EXISTS"

    assert _approve(client, incident_id, 1).status_code == 200
    after_approval = _submit_plan(client, incident_id, [amb])
    assert after_approval.status_code == 409
    assert after_approval.json()["code"] == "STALE_PLAN"


def test_intake_rejects_duplicate_and_unknown_resources(client):
    amb = _create_resource(client)
    incident_id = _create_incident(client)

    duplicate = _submit_plan(client, incident_id, [amb, amb])
    assert duplicate.status_code == 422
    assert duplicate.json()["code"] == "INVALID_RESOURCES"

    assert _submit_plan(client, incident_id, [amb, "AMB-99"]).status_code == 404
    assert _submit_plan(client, incident_id, []).status_code == 422
    assert _phase(client, incident_id) == "received"


def test_intake_does_not_reserve_resources(client):
    """A pending plan doesn't hold its resources: another incident's plan can
    still be approved with them, and the first approval then fails cleanly."""
    amb = _create_resource(client)
    first = _create_incident(client, "First")
    second = _create_incident(client, "Second")
    assert _submit_plan(client, first, [amb]).status_code == 201
    assert _submit_plan(client, second, [amb]).status_code == 201

    assert _approve(client, second, 1).status_code == 200
    late = _approve(client, first, 1)
    assert late.status_code == 409
    assert late.json()["code"] == "RESOURCE_UNAVAILABLE"
    assert _phase(client, first) == "awaiting_approval"


def test_intake_rejected_for_terminal_incident(client):
    amb = _create_resource(client)
    incident_id = _create_incident(client)
    assert client.post(f"/incidents/{incident_id}/cancel", json={}).status_code == 200
    assert _submit_plan(client, incident_id, [amb]).status_code == 409


# --- disruptions -----------------------------------------------------------


def test_disruption_requires_dispatched_incident_and_live_assignment(client):
    amb = _create_resource(client)
    other = _create_resource(client)
    incident_id = _create_incident(client)
    _submit_plan(client, incident_id, [amb])

    too_early = _disrupt(client, incident_id, amb)
    assert too_early.status_code == 409
    assert too_early.json()["code"] == "STALE_PLAN"

    _approve(client, incident_id, 1)
    not_assigned = _disrupt(client, incident_id, other)
    assert not_assigned.status_code == 409
    assert not_assigned.json()["code"] == "RESOURCE_NOT_ASSIGNED"
    assert _phase(client, incident_id) == "dispatched"


def test_repeated_disruption_keeps_stored_eta_as_previous(client, blocked_incident):
    incident_id, amb, _, _ = blocked_incident
    assert _disrupt(client, incident_id, amb, eta=31, previous=None).status_code == 200
    assignment = _live_assignments(incident_id)[amb]
    assert (assignment.previous_eta_minutes, assignment.eta_minutes) == (24, 31)


# --- replacement proposal --------------------------------------------------


def test_replacement_requires_blocked_phase(client):
    amb = _create_resource(client)
    spare = _create_resource(client)
    incident_id = _create_incident(client)
    _submit_plan(client, incident_id, [amb])
    _approve(client, incident_id, 1)

    response = _propose(client, incident_id, amb, [spare])
    assert response.status_code == 409
    assert response.json()["code"] == "STALE_PLAN"
    assert _phase(client, incident_id) == "dispatched"


def test_replacement_validation(client, blocked_incident):
    incident_id, amb, rescue, spare = blocked_incident

    keeps_failed = _propose(client, incident_id, amb, [amb, spare])
    assert keeps_failed.status_code == 422
    assert keeps_failed.json()["code"] == "INVALID_RESOURCES"

    stale = _propose(client, incident_id, amb, [spare, rescue], base_version=7)
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_PLAN"

    not_assigned = _propose(client, incident_id, spare, [rescue])
    assert not_assigned.status_code == 409
    assert not_assigned.json()["code"] == "RESOURCE_NOT_ASSIGNED"

    assert _propose(client, incident_id, amb, [spare, "AMB-99"]).status_code == 404
    assert _phase(client, incident_id) == "blocked"

    with SessionLocal() as db:
        assert db.query(Recommendation).filter(Recommendation.incident_id == incident_id).count() == 1


def test_second_replacement_proposal_conflicts_while_pending(client, blocked_incident):
    incident_id, amb, rescue, spare = blocked_incident
    assert _propose(client, incident_id, amb, [spare, rescue]).status_code == 201
    second = _propose(client, incident_id, amb, [spare])
    assert second.status_code == 409
    assert second.json()["code"] == "PENDING_PLAN_EXISTS"


def test_replacement_proposal_is_idempotent(client, blocked_incident):
    incident_id, amb, rescue, spare = blocked_incident
    first = _propose(client, incident_id, amb, [spare, rescue], analysis_revision="a-2")
    replay = _propose(client, incident_id, amb, [spare, rescue], analysis_revision="a-2")
    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]

    conflicting = _propose(client, incident_id, amb, [spare], analysis_revision="a-2")
    assert conflicting.status_code == 409
    assert conflicting.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_proposal_cannot_be_approved_with_stale_version(client, blocked_incident):
    incident_id, amb, rescue, spare = blocked_incident
    _propose(client, incident_id, amb, [spare, rescue])

    stale = _approve(client, incident_id, 1)
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_PLAN"
    assert _status(client, amb) == "DISPATCHED"
    assert _status(client, spare) == "AVAILABLE"


# --- replacement approval --------------------------------------------------


def test_replacement_approval_rolls_back_when_newcomer_unavailable(client, blocked_incident):
    incident_id, amb, rescue, spare = blocked_incident
    extra = _create_resource(client, "ambulance")
    _propose(client, incident_id, amb, [spare, extra, rescue])

    # extra gets taken by another incident between proposal and approval.
    other = _create_incident(client, "Elsewhere")
    _submit_plan(client, other, [extra])
    assert _approve(client, other, 1).status_code == 200

    response = _approve(client, incident_id, 2)
    assert response.status_code == 409
    assert response.json()["code"] == "RESOURCE_UNAVAILABLE"

    # Nothing changed: blocked resource still dispatched on its assignment,
    # spare not dispatched, proposal still pending.
    assert _status(client, amb) == "DISPATCHED"
    assert _status(client, spare) == "AVAILABLE"
    assert set(_live_assignments(incident_id)) == {amb, rescue}
    assert _phase(client, incident_id) == "awaiting_replacement"
    assert client.get(f"{BASE}/{incident_id}/recommendation").json()["state"] == "pending"


def test_replacement_plan_can_drop_a_resource_without_newcomers(client, blocked_incident):
    incident_id, amb, rescue, _ = blocked_incident
    assert _propose(client, incident_id, amb, [rescue]).status_code == 201
    assert _approve(client, incident_id, 2).status_code == 200
    assert set(_live_assignments(incident_id)) == {rescue}
    assert _status(client, amb) == "AVAILABLE"


def test_concurrent_replacement_approvals_apply_once(client, blocked_incident):
    incident_id, amb, rescue, spare = blocked_incident
    _propose(client, incident_id, amb, [spare, rescue])

    barrier = threading.Barrier(2)

    def attempt():
        barrier.wait()
        return _approve(client, incident_id, 2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [f.result() for f in [executor.submit(attempt), executor.submit(attempt)]]

    assert sorted(r.status_code for r in results) == [200, 409]
    with SessionLocal() as db:
        spare_live = (
            db.query(Assignment)
            .filter(Assignment.resource_id == spare, Assignment.status.in_(LIVE))
            .count()
        )
        superseded = (
            db.query(Assignment)
            .filter(Assignment.resource_id == amb, Assignment.status == AssignmentStatus.SUPERSEDED)
            .count()
        )
    assert (spare_live, superseded) == (1, 1)


def test_concurrent_replacement_proposals_create_one_version(client, blocked_incident):
    incident_id, amb, rescue, spare = blocked_incident
    barrier = threading.Barrier(2)

    def attempt(revision):
        barrier.wait()
        return _propose(client, incident_id, amb, [spare, rescue], analysis_revision=revision)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [f.result() for f in [executor.submit(attempt, "x"), executor.submit(attempt, "y")]]

    assert sorted(r.status_code for r in results) == [201, 409]
    with SessionLocal() as db:
        versions = sorted(
            r.version for r in db.query(Recommendation).filter(Recommendation.incident_id == incident_id)
        )
    assert versions == [1, 2]


def test_race_for_newcomer_between_two_incidents_cannot_double_book(client):
    """Two blocked incidents' replacements both want the same spare
    ambulance; exactly one approval can dispatch it."""
    spare = _create_resource(client, "ambulance")
    incidents = []
    for name in ("A", "B"):
        blocked = _create_resource(client, "ambulance")
        incident_id = _create_incident(client, name)
        _submit_plan(client, incident_id, [blocked])
        _approve(client, incident_id, 1)
        _disrupt(client, incident_id, blocked)
        assert _propose(client, incident_id, blocked, [spare]).status_code == 201
        incidents.append((incident_id, blocked))

    barrier = threading.Barrier(2)

    def attempt(incident_id):
        barrier.wait()
        return _approve(client, incident_id, 2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt, incident_id) for incident_id, _ in incidents]
        results = [f.result() for f in futures]

    assert sorted(r.status_code for r in results) == [200, 409]
    with SessionLocal() as db:
        assert (
            db.query(Assignment)
            .filter(Assignment.resource_id == spare, Assignment.status.in_(LIVE))
            .count()
            == 1
        )
    # The loser kept its original (blocked) responder — rollback was complete.
    loser_index = 0 if results[0].status_code == 409 else 1
    loser_incident, loser_blocked = incidents[loser_index]
    assert set(_live_assignments(loser_incident)) == {loser_blocked}
    assert _phase(client, loser_incident) == "awaiting_replacement"


# --- auth ------------------------------------------------------------------


def test_automation_key_can_propose_but_not_approve_replacement(client, blocked_incident, auth_settings):
    incident_id, amb, rescue, spare = blocked_incident
    auth_settings(
        auth_enabled=True,
        api_key="shared-secret",
        coordinator_api_key="coord-secret",
        automation_api_key="automation-secret",
    )
    automation = {"X-API-Key": "automation-secret"}

    proposed = client.post(
        f"{BASE}/{incident_id}/recommendation/replacement",
        json={
            "base_version": 1,
            "replacement_for": amb,
            "recommended_resources": [spare, rescue],
            "reason": "plan.replacementReason",
        },
        headers=automation,
    )
    assert proposed.status_code == 201

    denied = client.post(
        f"{BASE}/{incident_id}/recommendation/approve", json={"version": 2}, headers=automation
    )
    assert denied.status_code == 403
    # Checked via the DB: /resources itself requires the shared key here.
    assert spare not in _live_assignments(incident_id)

    unauthenticated = client.post(
        f"{BASE}/{incident_id}/recommendation/replacement",
        json={"base_version": 1, "replacement_for": amb, "recommended_resources": [spare], "reason": "x"},
    )
    assert unauthenticated.status_code == 401

    approved = client.post(
        f"{BASE}/{incident_id}/recommendation/approve",
        json={"version": 2},
        headers={"X-API-Key": "coord-secret"},
    )
    assert approved.status_code == 200
