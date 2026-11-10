"""Historical assignment references remain intact for unavailable resources."""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus, ResourceStatus
from app.models.incident import Incident
from app.models.resource import Resource


def _seed_history(client):
    incident = client.post("/incidents", json={
        "location": "Synthetic historical case", "type": "flood", "severity": "HIGH",
    })
    resource = client.post("/resources", json={
        "type": "ambulance", "location": "Synthetic depot",
    })
    assert incident.status_code == 201, incident.text
    assert resource.status_code == 201, resource.text
    incident_id = incident.json()["id"]
    resource_id = resource.json()["id"]
    # Insert a terminal historical assignment directly into the isolated
    # test database; this does not dispatch a resource or bypass a live gate.
    with SessionLocal() as db:
        db.add(Assignment(
            id="ASG-HISTORY-1", incident_id=incident_id,
            resource_id=resource_id, status=AssignmentStatus.COMPLETED,
            decision_source="test", approved_by="test-coordinator",
        ))
        db.commit()
    return incident_id, resource_id


def test_completed_assignment_keeps_unavailable_resource_reference(client):
    incident_id, resource_id = _seed_history(client)
    with SessionLocal() as db:
        resource = db.get(Resource, resource_id)
        resource.status = ResourceStatus.UNAVAILABLE
        db.commit()
    with SessionLocal() as db:
        historical = db.scalars(select(Assignment).where(
            Assignment.incident_id == incident_id
        )).one()
        assert historical.status == AssignmentStatus.COMPLETED
        assert historical.resource_id == resource_id
        assert db.get(Resource, historical.resource_id).status == ResourceStatus.UNAVAILABLE


def test_deleting_resource_referenced_by_history_is_rejected(client):
    _, resource_id = _seed_history(client)
    with SessionLocal() as db:
        db.delete(db.get(Resource, resource_id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    with SessionLocal() as db:
        assert db.get(Resource, resource_id) is not None
        assert db.get(Assignment, "ASG-HISTORY-1") is not None


def test_deleting_incident_referenced_by_history_is_rejected(client):
    incident_id, _ = _seed_history(client)
    with SessionLocal() as db:
        db.delete(db.get(Incident, incident_id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    with SessionLocal() as db:
        assert db.get(Incident, incident_id) is not None
        assert db.get(Assignment, "ASG-HISTORY-1") is not None
