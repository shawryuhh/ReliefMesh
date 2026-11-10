"""Model-level tests for the `recommendations` table added in migration
0f0c42fad357. No approve/modify/reject API exists yet (Phase 3), so these
write directly through SQLAlchemy.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.assignment import Assignment
from app.models.recommendation import Recommendation
from app.models.resource import Resource
from app.services.id_generator import next_assignment_id, next_recommendation_id


def _create_incident(client, location="Test Location"):
    response = client.post(
        "/incidents",
        json={"location": location, "type": "flood", "severity": "CRITICAL"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_resource(client, resource_type="ambulance", location="Depot"):
    response = client.post("/resources", json={"type": resource_type, "location": location})
    assert response.status_code == 201
    return response.json()["id"]


def test_recommendation_persists_with_version_and_defaults(client):
    incident_id = _create_incident(client)

    with SessionLocal() as db:
        rec_id = next_recommendation_id(db)
        rec = Recommendation(
            id=rec_id, incident_id=incident_id, version=1,
            recommended_resources=["AMB-02", "RESCUE-01"],
            reason="plan.reason", confidence=0.91, priority_score=94,
            explanation=[
                {"key": "explain.distance", "params": {"id": "AMB-02", "distance": 2.1}},
                {"key": "explain.eta", "params": {"id": "AMB-02", "eta": 6}},
            ],
        )
        db.add(rec)
        db.commit()

    with SessionLocal() as db:
        fetched = db.get(Recommendation, rec_id)
        assert fetched.state.value == "pending"
        assert fetched.version == 1
        assert fetched.recommended_resources == ["AMB-02", "RESCUE-01"]
        assert fetched.explanation[1]["params"]["eta"] == 6
        assert fetched.decided_by is None
        assert fetched.decided_at is None


def test_only_one_pending_recommendation_per_incident(client):
    incident_id = _create_incident(client)

    with SessionLocal() as db:
        db.add(Recommendation(
            id=next_recommendation_id(db), incident_id=incident_id, version=1,
            recommended_resources=["AMB-02", "RESCUE-01"], reason="plan.reason",
        ))
        db.commit()

    with SessionLocal() as db:
        db.add(Recommendation(
            id=next_recommendation_id(db), incident_id=incident_id, version=2,
            recommended_resources=["AMB-05", "RESCUE-01"], reason="plan.modified",
        ))
        with pytest.raises(IntegrityError):
            db.commit()


def test_second_pending_allowed_once_first_is_decided(client):
    incident_id = _create_incident(client)

    with SessionLocal() as db:
        v1_id = next_recommendation_id(db)
        db.add(Recommendation(
            id=v1_id, incident_id=incident_id, version=1,
            recommended_resources=["AMB-02", "RESCUE-01"], reason="plan.reason",
        ))
        db.commit()

    # Approving v1 (state transition only — no assignment side effects here,
    # that belongs to the Phase 3 approval transaction) frees the incident
    # up for a new pending recommendation, e.g. a replacement proposal.
    with SessionLocal() as db:
        v1 = db.get(Recommendation, v1_id)
        v1.state = "approved"
        db.commit()

    with SessionLocal() as db:
        db.add(Recommendation(
            id=next_recommendation_id(db), incident_id=incident_id, version=2,
            recommended_resources=["AMB-05", "RESCUE-01"],
            reason="plan.replacementReason", replacement_for_resource_id="AMB-02",
        ))
        db.commit()

    with SessionLocal() as db:
        states = {
            r.version: r.state.value
            for r in db.query(Recommendation).filter(Recommendation.incident_id == incident_id)
        }
        assert states == {1: "approved", 2: "pending"}


def _direct_assign(incident_id, resource_id):
    """Writes a live Assignment straight through the ORM, bypassing the
    approval-gated POST /assignments endpoint (Phase 4) — these tests are
    about Recommendation's own FK/columns, not the assignment-creation gate."""
    with SessionLocal() as db:
        assignment_id = next_assignment_id(db)
        db.add(Assignment(
            id=assignment_id, incident_id=incident_id, resource_id=resource_id,
            status="ASSIGNED", decision_source="ai", approved_by="coordinator",
        ))
        resource = db.get(Resource, resource_id)
        resource.status = "DISPATCHED"
        db.commit()
    return assignment_id


def test_recommendation_links_to_replaced_assignment(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    assignment_id = _direct_assign(incident_id, resource_id)

    with SessionLocal() as db:
        rec_id = next_recommendation_id(db)
        db.add(Recommendation(
            id=rec_id, incident_id=incident_id, version=2,
            recommended_resources=["AMB-05"], reason="plan.replacementReason",
            replacement_for_resource_id=resource_id, replaced_assignment_id=assignment_id,
        ))
        db.commit()

    with SessionLocal() as db:
        fetched = db.get(Recommendation, rec_id)
        assert fetched.replaced_assignment_id == assignment_id
        assert fetched.replacement_for_resource_id == resource_id


def test_assignment_carries_optional_eta_and_recommendation_link(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    assignment_id = _direct_assign(incident_id, resource_id)

    with SessionLocal() as db:
        rec_id = next_recommendation_id(db)
        db.add(Recommendation(
            id=rec_id, incident_id=incident_id, version=1,
            recommended_resources=[resource_id], reason="plan.reason",
        ))
        db.commit()

    with SessionLocal() as db:
        assignment = db.get(Assignment, assignment_id)
        assignment.recommendation_id = rec_id
        assignment.eta_minutes = 6
        assignment.distance_km = 2.1
        db.commit()

    with SessionLocal() as db:
        fetched = db.get(Assignment, assignment_id)
        assert fetched.recommendation_id == rec_id
        assert fetched.eta_minutes == 6
        assert fetched.distance_km == 2.1
        assert fetched.previous_eta_minutes is None

    # Existing assignments/resources are unaffected by the new nullable columns.
    with SessionLocal() as db:
        resource = db.get(Resource, resource_id)
        assert resource.status.value == "DISPATCHED"
