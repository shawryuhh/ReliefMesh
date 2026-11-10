"""The demo seed runs the canonical Krishna Apartments scenario through the
real service layer — against the isolated test DB here, never the dev DB."""

import pytest

from app.db.session import SessionLocal
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus
from app.models.incident import Incident
from app.models.recommendation import Recommendation
from app.models.resource import Resource
from scripts import seed_demo_data


def _seed(stop_at):
    with SessionLocal() as db:
        seed_demo_data.reset_tables(db)
        seed_demo_data.seed_fleet(db)
        seed_demo_data.seed_narrative_scenario(db, stop_at)


def test_full_seed_reaches_replaced_state():
    _seed("replaced")
    with SessionLocal() as db:
        incident = db.get(Incident, "INC-1042")
        assert incident.operational_phase.value == "dispatched"
        live = {
            a.resource_id
            for a in db.query(Assignment).filter(
                Assignment.incident_id == "INC-1042",
                Assignment.status.in_((AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)),
            )
        }
        assert live == {"AMB-05", "RESCUE-01"}
        assert db.get(Resource, "AMB-02").status.value == "AVAILABLE"
        assert db.get(Assignment, "ASG-887").resource_id == "AMB-02"
        assert db.get(Assignment, "ASG-887").status == AssignmentStatus.SUPERSEDED
        recs = db.query(Recommendation).order_by(Recommendation.version).all()
        assert [(r.id, r.version, r.state.value) for r in recs] == [
            ("REC-01", 1, "approved"),
            ("REC-02", 2, "approved"),
        ]
        assert recs[1].replacement_for_resource_id == "AMB-02"


@pytest.mark.parametrize(
    "stop_at, phase",
    [
        ("awaiting_approval", "awaiting_approval"),
        ("dispatched", "dispatched"),
        ("blocked", "blocked"),
        ("awaiting_replacement", "awaiting_replacement"),
    ],
)
def test_seed_can_stop_at_each_stage(stop_at, phase):
    _seed(stop_at)
    with SessionLocal() as db:
        assert db.get(Incident, "INC-1042").operational_phase.value == phase
