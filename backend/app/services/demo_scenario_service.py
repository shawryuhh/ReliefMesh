"""End-to-end backend demo scenario service backed by PostgreSQL and `ai/main.py`.

Drives the canonical `INC-1042` lifecycle (`receive`, `merge`, `priority`,
`recommend`, `request`, `approve`, `block`, `replan`, `replace`,
`approveReplacement`, `resolve`) against real PostgreSQL tables using the
backend service layer (`incident_service`, `recommendation_service`,
`disruption_service`, `assignment_service`) and the AI engine (`ai/main.py`).

Safety invariants:
- `approve` and `approveReplacement` require coordinator authentication and
  can never be triggered by AI or n8n automation keys.
- Repeated automation events are idempotent and never create duplicate
  incidents, recommendations, or assignments.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ApprovalRequiredError,
    ConflictError,
    InvalidResourcesError,
    NotFoundError,
    ResourceUnavailableError,
    StaleRecommendationError,
    ValidationFailedError,
)
from app.models.action_log import ActionLog
from app.models.assignment import Assignment
from app.models.enums import (
    AssignmentStatus,
    IncidentStatus,
    OperationalPhase,
    RecommendationState,
    ResourceStatus,
    Severity,
)
from app.models.incident import Incident
from app.models.recommendation import Recommendation
from app.models.report import Report
from app.models.resource import Resource
from app.schemas.disruption import DisruptionReport
from app.schemas.recommendation import (
    RecommendationApprove,
    RecommendationModify,
    RecommendationReject,
)
from app.services import (
    ai_engine_service,
    disruption_service,
    id_generator,
    incident_service,
    recommendation_service,
)
from app.services.action_log_service import record_action
from app.services.operational_revision import (
    bump_operational_revision,
    current_operational_revision,
)

DEMO_STEPS = [
    "receive",
    "merge",
    "priority",
    "recommend",
    "request",
    "approve",
    "block",
    "replan",
    "replace",
    "approveReplacement",
    "resolve",
]

# Resource default ETAs and distances (in minutes and km) relative to the Bengaluru sector
FLEET_DEFAULTS: dict[str, dict[str, Any]] = {
    "AMB-01": {"eta": 8, "distanceKm": 3.2},
    "AMB-02": {"eta": 6, "distanceKm": 2.1},
    "AMB-03": {"eta": 7, "distanceKm": 2.8},
    "AMB-04": {"eta": 12, "distanceKm": 5.4},
    "AMB-05": {"eta": 9, "distanceKm": 3.8},
    "AMB-06": {"eta": 14, "distanceKm": 6.0},
    "AMB-07": {"eta": 11, "distanceKm": 4.2},
    "RESCUE-01": {"eta": 7},
    "RESCUE-02": {"eta": 9},
    "RESCUE-03": {"eta": 11},
    "RESCUE-04": {"eta": 13},
    "RESCUE-05": {"eta": 15},
    "HOSP-01": {"name": "South City Medical Centre"},
    "HOSP-02": {"name": "District Emergency Hospital"},
    "HOSP-03": {"name": "Community Care Hospital"},
    "SHELTER-01": {"name": "Agara Relief Centre"},
    "SHELTER-02": {"name": "HSR Public School"},
    "SHELTER-03": {"name": "Koramangala Community Hall"},
    "SHELTER-04": {"name": "Bellandur Relief Camp"},
}

BACKGROUND_INCIDENTS: list[tuple[str, str, float, float, str, int, int, int, str]] = [
    (
        "INC-1041",
        "Ejipura low-lying settlement",
        12.942,
        77.622,
        "evacuation",
        5,
        89,
        18,
        "Water has reached the ground floor. Eighteen residents need help moving to a shelter.",
    ),
    (
        "INC-1040",
        "HSR Layout · Sector 2",
        12.912,
        77.642,
        "medical",
        4,
        85,
        1,
        "पानी के कारण रास्ता बंद है। मेरे पिता को साँस लेने में तकलीफ़ हो रही है।",
    ),
    (
        "INC-1039",
        "Bellandur service road",
        12.928,
        77.675,
        "flood",
        4,
        78,
        6,
        "Six workers are stranded near the service road. Water is rising.",
    ),
    (
        "INC-1038",
        "Agara village",
        12.925,
        77.650,
        "supplies",
        3,
        64,
        24,
        "We need drinking water and dry food at the community hall.",
    ),
    (
        "INC-1037",
        "Madiwala market",
        12.919,
        77.616,
        "evacuation",
        3,
        61,
        8,
        "Eight shopkeepers cannot cross the flooded market entrance.",
    ),
    (
        "INC-1036",
        "Koramangala · 6th Block",
        12.938,
        77.613,
        "medical",
        4,
        81,
        2,
        "Two people have minor injuries after a wall collapsed.",
    ),
    (
        "INC-1035",
        "Sarjapur junction",
        12.918,
        77.663,
        "landslide",
        3,
        57,
        4,
        "Debris is blocking the approach road. Four residents are safe upstairs.",
    ),
    (
        "INC-1034",
        "BTM Layout · 2nd Stage",
        12.907,
        77.610,
        "supplies",
        2,
        42,
        12,
        "Families at the school shelter need blankets and medication.",
    ),
    (
        "INC-1033",
        "Iblur community centre",
        12.921,
        77.666,
        "evacuation",
        2,
        35,
        7,
        "Seven residents have reached the community centre safely.",
    ),
]

_DEMO_LOCK = threading.Lock()
_DEMO_RUNTIME_STATE: dict[str, Any] = {
    "scenario": "normal",
    "busy_resource_ids": {"AMB-06", "HOSP-03"},
    "idempotency_keys": {},
}


def _derive_demo_index(db: Session) -> int:
    """Derives the canonical 0..11 demo step index deterministically from PostgreSQL state."""
    incident = db.get(Incident, "INC-1042")
    if incident is None:
        return 0

    phase = incident.operational_phase
    if phase in (OperationalPhase.RECEIVED, OperationalPhase.ANALYZING):
        return 2 if (incident.duplicate_count or 0) > 0 else 1
    if phase == OperationalPhase.PRIORITIZED:
        return 3
    if phase == OperationalPhase.RECOMMENDED:
        return 4
    if phase in (OperationalPhase.AWAITING_APPROVAL, OperationalPhase.REJECTED):
        return 5
    if phase == OperationalPhase.REPLANNING:
        return 8
    if phase == OperationalPhase.AWAITING_REPLACEMENT:
        return 9
    if phase == OperationalPhase.RESOLVED:
        return 11

    latest_rec = db.scalars(
        select(Recommendation)
        .where(Recommendation.incident_id == "INC-1042")
        .order_by(Recommendation.version.desc())
        .limit(1)
    ).first()
    if phase == OperationalPhase.BLOCKED:
        if (
            latest_rec is not None
            and latest_rec.replacement_for_resource_id is not None
            and latest_rec.state == RecommendationState.REJECTED
        ):
            return 9
        return 7
    if phase == OperationalPhase.DISPATCHED:
        if latest_rec is not None and latest_rec.replacement_for_resource_id is not None:
            return 10
        return 6
    return 5


def _severity_enum(score: int) -> Severity:
    if score >= 5:
        return Severity.CRITICAL
    if score == 4:
        return Severity.HIGH
    if score == 3:
        return Severity.MEDIUM
    return Severity.LOW


def _require_operational() -> None:
    scenario = _DEMO_RUNTIME_STATE["scenario"]
    if scenario in ("api_failure", "loading"):
        raise ConflictError("Operational API is simulated as unavailable.", code="API_FAILURE")
    if scenario == "empty_resources":
        raise ResourceUnavailableError("No available responder resources in current scenario.")
    if scenario == "empty_incidents":
        raise NotFoundError("No active incidents in current scenario.")
    if scenario == "offline":
        raise ConflictError("Automation layer is currently offline.", code="AUTOMATION_OFFLINE")


def reset_demo_database(db: Session, *, for_run: bool = False) -> dict[str, Any]:
    """Resets and seeds the full 19-unit Bengaluru fleet and 10 incidents in PostgreSQL."""
    with _DEMO_LOCK:
        tables = ["incidents", "resources", "assignments", "action_logs", "reports", "recommendations"]
        db.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        for seq_name in ("report_seq", "recommendation_seq"):
            db.execute(text(f"SELECT setval('{seq_name}', 1, false)"))
        db.execute(text("SELECT setval('incident_seq', 1041)"))
        db.execute(text("SELECT setval('assignment_seq', 886)"))

        now = datetime.now(timezone.utc)

        # 1. Seed 7 ambulances, 5 rescue teams, 3 hospitals, 4 shelters (19 total)
        amb_lats = [12.953, 12.949, 12.921, 12.906, 12.936, 12.916, 12.940]
        amb_lngs = [77.640, 77.614, 77.605, 77.655, 77.664, 77.674, 77.649]
        for i in range(7):
            rid = f"AMB-0{i + 1}"
            caps = ["basic_life_support"] if i % 3 == 0 else ["advanced_life_support"]
            status = (
                ResourceStatus.DISPATCHED
                if i == 2
                else ResourceStatus.ACTIVE
                if i == 5
                else ResourceStatus.AVAILABLE
            )
            db.add(
                Resource(
                    id=rid,
                    type="ambulance",
                    location=f"Bengaluru Ambulance Depot {i + 1}",
                    latitude=amb_lats[i],
                    longitude=amb_lngs[i],
                    capabilities=caps,
                    capacity=2,
                    status=status,
                )
            )

        for i in range(5):
            rid = f"RESCUE-0{i + 1}"
            caps = ["water_rescue", "first_aid"] if i < 3 else ["evacuation", "first_aid"]
            status = (
                ResourceStatus.ACTIVE
                if i == 3
                else ResourceStatus.UNAVAILABLE
                if i == 4
                else ResourceStatus.AVAILABLE
            )
            db.add(
                Resource(
                    id=rid,
                    type="rescue",
                    location=f"Bengaluru Rescue Base {i + 1}",
                    latitude=round(12.928 + i * 0.004, 4),
                    longitude=round(77.602 + i * 0.017, 4),
                    capabilities=caps,
                    capacity=6,
                    status=status,
                )
            )

        hosp_names = [
            "South City Medical Centre",
            "District Emergency Hospital",
            "Community Care Hospital",
        ]
        hosp_caps = [18, 32, 12]
        for i, name in enumerate(hosp_names):
            rid = f"HOSP-0{i + 1}"
            db.add(
                Resource(
                    id=rid,
                    type="hospital",
                    location=name,
                    latitude=round(12.914 + i * 0.019, 4),
                    longitude=round(77.630 + i * 0.010, 4),
                    capabilities=["emergency_care", "icu"],
                    capacity=hosp_caps[i],
                    status=ResourceStatus.ACTIVE if i == 2 else ResourceStatus.AVAILABLE,
                )
            )

        shelter_names = [
            "Agara Relief Centre",
            "HSR Public School",
            "Koramangala Community Hall",
            "Bellandur Relief Camp",
        ]
        shelter_caps = [120, 80, 150, 60]
        for i, name in enumerate(shelter_names):
            rid = f"SHELTER-0{i + 1}"
            db.add(
                Resource(
                    id=rid,
                    type="shelter",
                    location=name,
                    latitude=round(12.904 + i * 0.012, 4),
                    longitude=round(77.620 + i * 0.014, 4),
                    capabilities=["shelter", "supplies"],
                    capacity=shelter_caps[i],
                    status=ResourceStatus.AVAILABLE,
                )
            )

        db.flush()

        # 2. Seed 9 background incidents and their reports
        for idx, (inc_id, loc, lat, lng, inc_type, sev_score, prio, people, text_body) in enumerate(
            BACKGROUND_INCIDENTS
        ):
            needs = (
                ["ambulance"]
                if inc_type == "medical"
                else ["supplies"]
                if inc_type == "supplies"
                else ["water_rescue", "shelter"]
            )
            phase = (
                OperationalPhase.RESOLVED
                if idx == 8
                else OperationalPhase.DISPATCHED
                if idx == 5
                else OperationalPhase.RECEIVED
            )
            inc_status = (
                IncidentStatus.RESOLVED
                if idx == 8
                else IncidentStatus.ASSIGNED
                if idx == 5
                else IncidentStatus.UNASSIGNED
            )
            db.add(
                Incident(
                    id=inc_id,
                    location=loc,
                    latitude=lat,
                    longitude=lng,
                    type=inc_type,
                    severity=_severity_enum(sev_score),
                    severity_score=sev_score,
                    priority_score=prio,
                    people_affected=people,
                    needs=needs,
                    confidence=round(0.82 + idx / 100.0, 2),
                    status=inc_status,
                    operational_phase=phase,
                    vulnerabilities=["elderly_mobility"] if idx == 1 else [],
                    duplicate_count=0,
                )
            )
            db.flush()
            db.add(
                Report(
                    id=f"RPT-{inc_id}",
                    incident_id=inc_id,
                    original_text=text_body,
                    original_language="hi" if idx == 1 else "en",
                    translated_text=(
                        "The road is blocked by water. My father is having difficulty breathing."
                        if idx == 1
                        else None
                    ),
                    translated_language="en" if idx == 1 else None,
                    received_at=now,
                )
            )

        # Seed existing assignment ASN-SEED for INC-1036 -> AMB-03
        db.add(
            Assignment(
                id="ASN-SEED",
                incident_id="INC-1036",
                resource_id="AMB-03",
                status=AssignmentStatus.ASSIGNED,
                decision_source="coordinator_approval",
                approved_by="coordinator",
                eta_minutes=7,
                distance_km=2.8,
                assigned_at=now,
            )
        )

        _DEMO_RUNTIME_STATE["scenario"] = "normal"
        _DEMO_RUNTIME_STATE["idempotency_keys"] = {}

        if for_run:
            bump_operational_revision(db)
            db.commit()
            return get_demo_dashboard_snapshot(db)

        # 3. Default state (for_run=False): seed INC-1042 at step 5 (awaiting_approval)
        db.add(
            Incident(
                id="INC-1042",
                location="Krishna Apartments Block C",
                latitude=12.9347,
                longitude=77.6269,
                type="flood",
                severity=Severity.CRITICAL,
                severity_score=5,
                priority_score=94,
                people_affected=3,
                needs=["ambulance", "water_rescue"],
                confidence=0.91,
                status=IncidentStatus.UNASSIGNED,
                operational_phase=OperationalPhase.AWAITING_APPROVAL,
                vulnerabilities=["elderly_mobility"],
                duplicate_count=2,
            )
        )
        db.flush()
        db.add(
            Report(
                id="RPT-1042",
                incident_id="INC-1042",
                original_text="Water entering Krishna Apartments Block C. My grandmother cannot walk.",
                original_language="en",
                received_at=now,
            )
        )
        rec_id = id_generator.next_recommendation_id(db)
        db.add(
            Recommendation(
                id=rec_id,
                incident_id="INC-1042",
                version=1,
                state=RecommendationState.PENDING,
                recommended_resources=["AMB-02", "RESCUE-01"],
                reason="plan.reason",
                explanation=[
                    {"key": "explain.distance", "params": {"id": "AMB-02", "distance": 2.1}},
                    {"key": "explain.available", "params": {"id": "AMB-02"}},
                    {"key": "explain.als", "params": {"id": "AMB-02"}},
                    {"key": "explain.eta", "params": {"id": "AMB-02", "eta": 6}},
                    {"key": "explain.water", "params": {"id": "RESCUE-01"}},
                    {"key": "explain.priority", "params": {}},
                ],
                confidence=0.91,
                priority_score=94,
                analysis_revision="seed-analysis-1",
            )
        )

        seed_events = [
            ("intake", "incident_received"),
            ("intake", "duplicates_merged"),
            ("ai", "priority_updated"),
            ("ai", "recommendation_generated"),
            ("ai", "approval_requested"),
        ]
        for idx, (source, action) in enumerate(seed_events):
            db.add(
                ActionLog(
                    source=source,
                    action=action,
                    incident_id="INC-1042",
                    timestamp=now - timedelta(seconds=(5 - idx) * 45),
                    log_metadata={
                        "id": "INC-1042",
                        "resources": "AMB-02 + RESCUE-01",
                        "priority": 94,
                        "count": 2,
                    },
                )
            )

        bump_operational_revision(db)
        db.commit()
        return get_demo_dashboard_snapshot(db)


def ensure_demo_seeded(db: Session) -> None:
    """Seeds the demo database if resources have not been populated yet."""
    has_amb_02 = db.get(Resource, "AMB-02") is not None
    has_inc_1041 = db.get(Incident, "INC-1041") is not None
    if not has_amb_02 or not has_inc_1041:
        reset_demo_database(db, for_run=False)


def set_demo_scenario(db: Session, scenario: str) -> dict[str, Any]:
    ensure_demo_seeded(db)
    valid = {
        "normal",
        "stale",
        "offline",
        "api_failure",
        "empty_incidents",
        "empty_resources",
        "loading",
    }
    if scenario not in valid:
        raise ValidationFailedError(f"Unsupported demo scenario '{scenario}'.")
    _DEMO_RUNTIME_STATE["scenario"] = scenario
    if scenario == "api_failure":
        return {"scenario": scenario}
    return get_demo_dashboard_snapshot(db)


def execute_demo_step(
    db: Session,
    step: str,
    *,
    actor: str = "automation",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Executes one step of the canonical 11-step `INC-1042` lifecycle."""
    ensure_demo_seeded(db)
    _require_operational()

    if step not in DEMO_STEPS:
        raise ValidationFailedError(f"Unknown demo step '{step}'.")

    # Enforce the human approval gate: AI/n8n automation can NEVER execute
    # `approve` or `approveReplacement`.
    if step in ("approve", "approveReplacement") and actor != "coordinator":
        raise ApprovalRequiredError(
            f"Step '{step}' requires human coordinator approval and cannot be executed by '{actor}'."
        )

    with _DEMO_LOCK:
        if idempotency_key and idempotency_key in _DEMO_RUNTIME_STATE["idempotency_keys"]:
            return get_demo_dashboard_snapshot(db)

        current_idx = _derive_demo_index(db)
        expected_step = DEMO_STEPS[current_idx] if current_idx < len(DEMO_STEPS) else None
        if expected_step != step:
            raise ConflictError(
                f"Demo step '{step}' is out of order (expected '{expected_step}').",
                code="STEP_OUT_OF_ORDER",
            )

        now = datetime.now(timezone.utc)
        incident = db.get(Incident, "INC-1042")

        if step == "receive":
            if incident is not None:
                raise ConflictError("INC-1042 has already been received.", code="STEP_OUT_OF_ORDER")
            extracted = ai_engine_service.extract_synthetic_incident(
                "Water entering Krishna Apartments Block C. My grandmother cannot walk.",
                incident_id="INC-1042",
            )
            incident = Incident(
                id="INC-1042",
                location=extracted["location"],
                latitude=extracted["latitude"],
                longitude=extracted["longitude"],
                type=extracted["incident_type"],
                severity=Severity.CRITICAL,
                severity_score=5,
                priority_score=0,
                people_affected=extracted["people_affected"],
                needs=["ambulance", "water_rescue"],
                confidence=extracted["confidence"],
                status=IncidentStatus.UNASSIGNED,
                operational_phase=OperationalPhase.ANALYZING,
                vulnerabilities=["elderly_mobility"],
                duplicate_count=0,
            )
            db.add(incident)
            db.flush()
            db.add(
                Report(
                    id="RPT-1042",
                    incident_id="INC-1042",
                    original_text="Water entering Krishna Apartments Block C. My grandmother cannot walk.",
                    original_language="en",
                    received_at=now,
                )
            )
            record_action(
                db,
                source="intake",
                action="incident_received",
                incident_id="INC-1042",
                metadata={"id": "INC-1042"},
            )
            bump_operational_revision(db)
            db.commit()

        elif step == "merge":
            if incident is None:
                raise NotFoundError("Incident 'INC-1042' not found.")
            dedup = ai_engine_service.deduplicate_synthetic_incident(
                incident_id="INC-1042", duplicate_count=2
            )
            incident.duplicate_count = dedup["duplicate_count"]
            record_action(
                db,
                source="intake",
                action="duplicates_merged",
                incident_id="INC-1042",
                metadata={"id": "INC-1042", "count": dedup["duplicate_count"]},
            )
            bump_operational_revision(db)
            db.commit()

        elif step == "priority":
            if incident is None:
                raise NotFoundError("Incident 'INC-1042' not found.")
            scored = ai_engine_service.score_incident_with_ai(
                incident_id="INC-1042",
                duplicate_count=incident.duplicate_count,
                confidence=incident.confidence or 0.91,
            )
            incident.priority_score = scored["priority_score"]
            incident.operational_phase = OperationalPhase.PRIORITIZED
            record_action(
                db,
                source="ai",
                action="priority_updated",
                incident_id="INC-1042",
                metadata={"id": "INC-1042", "priority": scored["priority_score"]},
            )
            bump_operational_revision(db)
            db.commit()

        elif step == "recommend":
            if incident is None:
                raise NotFoundError("Incident 'INC-1042' not found.")
            available_rows = db.scalars(
                select(Resource).where(Resource.status == ResourceStatus.AVAILABLE)
            ).all()
            candidate_dicts = [
                {
                    "id": r.id,
                    "type": r.type,
                    "location": r.location,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "capabilities": r.capabilities,
                    "capacity": r.capacity,
                    "eta": FLEET_DEFAULTS.get(r.id, {}).get("eta"),
                }
                for r in available_rows
            ]
            ai_plan = ai_engine_service.recommend_resources_with_ai(
                incident_id="INC-1042",
                available_resources=candidate_dicts,
                analysis_revision="demo-rec-v1",
            )
            rec_id = id_generator.next_recommendation_id(db)
            db.add(
                Recommendation(
                    id=rec_id,
                    incident_id="INC-1042",
                    version=1,
                    state=RecommendationState.PENDING,
                    recommended_resources=ai_plan["recommended_resources"],
                    reason=ai_plan["reason"],
                    explanation=ai_plan["explanation"],
                    confidence=ai_plan["confidence"],
                    priority_score=ai_plan["priority_score"],
                    analysis_revision=ai_plan["analysis_revision"],
                )
            )
            incident.operational_phase = OperationalPhase.RECOMMENDED
            record_action(
                db,
                source="ai",
                action="recommendation_generated",
                incident_id="INC-1042",
                metadata={
                    "id": "INC-1042",
                    "resources": " + ".join(ai_plan["recommended_resources"]),
                },
            )
            bump_operational_revision(db)
            db.commit()

        elif step == "request":
            if incident is None:
                raise NotFoundError("Incident 'INC-1042' not found.")
            incident.operational_phase = OperationalPhase.AWAITING_APPROVAL
            record_action(
                db,
                source="ai",
                action="approval_requested",
                incident_id="INC-1042",
                metadata={"id": "INC-1042"},
            )
            bump_operational_revision(db)
            db.commit()

        elif step in ("approve", "approveReplacement"):
            if incident is None:
                raise NotFoundError("Incident 'INC-1042' not found.")
            current_rec = recommendation_service.get_current_recommendation(db, "INC-1042")
            approve_demo_recommendation(db, "INC-1042", current_rec.version, approved_by=actor)

        elif step == "block":
            if incident is None:
                raise NotFoundError("Incident 'INC-1042' not found.")
            live_amb = db.scalars(
                select(Assignment).where(
                    Assignment.incident_id == "INC-1042",
                    Assignment.resource_id == "AMB-02",
                    Assignment.status.in_((AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)),
                )
            ).first()
            if live_amb is None:
                raise ConflictError(
                    "Canonical roadblock requires AMB-02 to be dispatched to INC-1042.",
                    code="CANONICAL_MISMATCH",
                )
            disruption_service.report_disruption(
                db,
                "INC-1042",
                DisruptionReport(resource_id="AMB-02", eta_minutes=24, previous_eta_minutes=6),
            )

        elif step == "replan":
            if incident is None:
                raise NotFoundError("Incident 'INC-1042' not found.")
            incident.operational_phase = OperationalPhase.REPLANNING
            record_action(
                db,
                source="ai",
                action="replanning_started",
                incident_id="INC-1042",
                metadata={"id": "INC-1042", "resources": "AMB-02"},
            )
            bump_operational_revision(db)
            db.commit()

        elif step == "replace":
            if incident is None:
                raise NotFoundError("Incident 'INC-1042' not found.")
            current_rec = db.scalars(
                select(Recommendation)
                .where(Recommendation.incident_id == "INC-1042")
                .order_by(Recommendation.version.desc())
                .limit(1)
            ).first()
            if current_rec is None:
                raise StaleRecommendationError("No approved recommendation on INC-1042 to replace.")

            # Candidate resources: all AVAILABLE resources + continuing RESCUE-01
            candidate_rows = db.scalars(
                select(Resource).where(
                    (Resource.status == ResourceStatus.AVAILABLE) | (Resource.id == "RESCUE-01")
                )
            ).all()
            candidate_dicts = [
                {
                    "id": r.id,
                    "type": r.type,
                    "location": r.location,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "capabilities": r.capabilities,
                    "capacity": r.capacity,
                    "eta": FLEET_DEFAULTS.get(r.id, {}).get("eta"),
                }
                for r in candidate_rows
            ]
            ai_replacement = ai_engine_service.recommend_resources_with_ai(
                incident_id="INC-1042",
                available_resources=candidate_dicts,
                replacement_for="AMB-02",
                analysis_revision="demo-rec-v2",
            )
            live_amb = db.scalars(
                select(Assignment).where(
                    Assignment.incident_id == "INC-1042",
                    Assignment.resource_id == "AMB-02",
                    Assignment.status.in_((AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)),
                )
            ).first()
            rec_id = id_generator.next_recommendation_id(db)
            db.add(
                Recommendation(
                    id=rec_id,
                    incident_id="INC-1042",
                    version=current_rec.version + 1,
                    state=RecommendationState.PENDING,
                    recommended_resources=ai_replacement["recommended_resources"],
                    reason=ai_replacement["reason"],
                    explanation=ai_replacement["explanation"],
                    confidence=ai_replacement["confidence"],
                    priority_score=ai_replacement["priority_score"],
                    replacement_for_resource_id="AMB-02",
                    replaced_assignment_id=live_amb.id if live_amb else None,
                    analysis_revision=ai_replacement["analysis_revision"],
                )
            )
            incident.operational_phase = OperationalPhase.AWAITING_REPLACEMENT
            record_action(
                db,
                source="ai",
                action="replacement_recommended",
                incident_id="INC-1042",
                metadata={"id": "INC-1042", "resources": "AMB-05", "eta": 9},
            )
            record_action(
                db,
                source="ai",
                action="approval_requested",
                incident_id="INC-1042",
                metadata={"id": "INC-1042"},
            )
            bump_operational_revision(db)
            db.commit()

        elif step == "resolve":
            incident_service.resolve_incident(
                db,
                "INC-1042",
                "All three residents evacuated safely from Krishna Apartments Block C.",
            )

        if idempotency_key:
            _DEMO_RUNTIME_STATE["idempotency_keys"][idempotency_key] = step

        return get_demo_dashboard_snapshot(db)


def approve_demo_recommendation(
    db: Session,
    incident_id: str,
    version: int,
    *,
    approved_by: str,
) -> dict[str, Any]:
    """Approves a pending recommendation through the real service layer and updates demo state."""
    ensure_demo_seeded(db)
    _require_operational()
    if approved_by != "coordinator":
        raise ApprovalRequiredError("Only an authenticated coordinator can approve recommendations.")

    recommendation_service.approve_recommendation(
        db, incident_id, RecommendationApprove(version=version), approved_by
    )

    # Populate default ETAs and distances on newly created live assignments
    live_assignments = db.scalars(
        select(Assignment).where(
            Assignment.incident_id == incident_id,
            Assignment.status.in_((AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)),
        )
    ).all()
    updated_eta = False
    for a in live_assignments:
        defaults = FLEET_DEFAULTS.get(a.resource_id, {})
        if a.eta_minutes is None and "eta" in defaults:
            a.eta_minutes = defaults["eta"]
            updated_eta = True
        if a.distance_km is None and "distanceKm" in defaults:
            a.distance_km = defaults["distanceKm"]
            updated_eta = True
    if updated_eta:
        bump_operational_revision(db)
        db.commit()

    return get_demo_dashboard_snapshot(db)


def modify_demo_recommendation(
    db: Session,
    incident_id: str,
    resource_ids: list[str],
    version: int,
    *,
    modified_by: str,
) -> dict[str, Any]:
    ensure_demo_seeded(db)
    _require_operational()
    if modified_by != "coordinator":
        raise ApprovalRequiredError("Only an authenticated coordinator can modify recommendations.")
    recommendation_service.modify_recommendation(
        db,
        incident_id,
        RecommendationModify(version=version, recommended_resources=resource_ids),
        modified_by,
    )
    return get_demo_dashboard_snapshot(db)


def reject_demo_recommendation(
    db: Session,
    incident_id: str,
    reason: str,
    version: int,
    *,
    rejected_by: str,
) -> dict[str, Any]:
    ensure_demo_seeded(db)
    _require_operational()
    if rejected_by != "coordinator":
        raise ApprovalRequiredError("Only an authenticated coordinator can reject recommendations.")
    recommendation_service.reject_recommendation(
        db,
        incident_id,
        RecommendationReject(version=version, reason=reason),
        rejected_by,
    )
    return get_demo_dashboard_snapshot(db)


def create_demo_assignment(
    db: Session,
    incident_id: str,
    resource_id: str,
    *,
    actor: str = "coordinator",
) -> dict[str, Any]:
    """Idempotently creates or returns an assignment for an approved recommendation."""
    ensure_demo_seeded(db)
    _require_operational()
    incident = db.get(Incident, incident_id)
    if incident is None or incident.operational_phase != OperationalPhase.DISPATCHED:
        raise ApprovalRequiredError(
            f"Incident '{incident_id}' does not have an approved dispatch plan."
        )
    rec = db.scalars(
        select(Recommendation)
        .where(Recommendation.incident_id == incident_id)
        .order_by(Recommendation.version.desc())
        .limit(1)
    ).first()
    if (
        rec is None
        or rec.state != RecommendationState.APPROVED
        or resource_id not in rec.recommended_resources
    ):
        raise ApprovalRequiredError(
            f"Resource '{resource_id}' is not covered by an approved recommendation for '{incident_id}'."
        )
    existing = db.scalars(
        select(Assignment).where(
            Assignment.incident_id == incident_id,
            Assignment.resource_id == resource_id,
            Assignment.status.in_((AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)),
        )
    ).first()
    if existing is not None:
        return {
            "id": existing.id,
            "incidentId": existing.incident_id,
            "resourceId": existing.resource_id,
            "approvedBy": "coordinator",
            "createdAt": existing.assigned_at.isoformat(),
            "status": "dispatched",
        }
    raise ResourceUnavailableError(f"Resource '{resource_id}' is not available for dispatch.")


def get_demo_dashboard_snapshot(db: Session) -> dict[str, Any]:
    """Builds the complete frontend `DashboardSnapshot` from PostgreSQL."""
    ensure_demo_seeded(db)
    scenario = _DEMO_RUNTIME_STATE["scenario"]
    if scenario == "api_failure":
        raise ConflictError("Simulated API failure.", code="API_FAILURE")

    now = datetime.now(timezone.utc)
    incidents_rows = db.scalars(select(Incident)).all()
    reports_rows = db.scalars(select(Report).order_by(Report.received_at.asc())).all()
    resources_rows = db.scalars(select(Resource).order_by(Resource.id.asc())).all()
    assignments_rows = db.scalars(select(Assignment).order_by(Assignment.assigned_at.asc())).all()
    recommendations_rows = db.scalars(
        select(Recommendation).order_by(Recommendation.version.desc())
    ).all()
    actions_rows = db.scalars(
        select(ActionLog).order_by(ActionLog.timestamp.asc(), ActionLog.id.asc())
    ).all()

    reports_by_incident: dict[str, list[dict[str, Any]]] = {}
    for r in reports_rows:
        item: dict[str, Any] = {
            "id": r.id,
            "originalText": r.original_text,
            "originalLanguage": r.original_language or "en",
            "receivedAt": r.received_at.isoformat(),
        }
        if r.translated_text:
            item["translatedText"] = r.translated_text
        if r.translated_language:
            item["translatedLanguage"] = r.translated_language
        reports_by_incident.setdefault(r.incident_id, []).append(item)

    incidents: list[dict[str, Any]] = []
    if scenario != "empty_incidents":
        for inc in incidents_rows:
            incidents.append(
                {
                    "id": inc.id,
                    "location": inc.location,
                    "latitude": inc.latitude or 12.9347,
                    "longitude": inc.longitude or 77.6269,
                    "type": inc.type if inc.type in ("flood", "medical", "evacuation", "supplies", "landslide") else "flood",
                    "severity": inc.severity_score or 5,
                    "priority": inc.priority_score or 0,
                    "people": inc.people_affected or 1,
                    "needs": list(inc.needs or []),
                    "confidence": inc.confidence if inc.confidence is not None else 0.9,
                    "status": inc.operational_phase.value,
                    "vulnerabilities": list(inc.vulnerabilities or []),
                    "duplicates": inc.duplicate_count or 0,
                    "reports": reports_by_incident.get(inc.id, []),
                }
            )
    incidents.sort(key=lambda item: item["priority"], reverse=True)

    live_assignment_by_resource: dict[str, Assignment] = {}
    for a in assignments_rows:
        if a.status in (AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE):
            live_assignment_by_resource[a.resource_id] = a

    resources: list[dict[str, Any]] = []
    busy_ids = _DEMO_RUNTIME_STATE["busy_resource_ids"]
    for res in resources_rows:
        defaults = FLEET_DEFAULTS.get(res.id, {})
        live_a = live_assignment_by_resource.get(res.id)
        if scenario == "empty_resources" and res.status == ResourceStatus.AVAILABLE:
            mapped_status = "unavailable"
        elif res.id in busy_ids and res.status == ResourceStatus.ACTIVE:
            mapped_status = "busy"
        elif res.status == ResourceStatus.AVAILABLE:
            mapped_status = "available"
        elif res.status == ResourceStatus.DISPATCHED:
            mapped_status = "dispatched"
        elif res.status == ResourceStatus.ACTIVE:
            mapped_status = "active"
        else:
            mapped_status = "unavailable"

        eta = (
            live_a.eta_minutes
            if live_a and live_a.eta_minutes is not None
            else defaults.get("eta")
        )
        distance_km = (
            live_a.distance_km
            if live_a and live_a.distance_km is not None
            else defaults.get("distanceKm")
        )
        res_item: dict[str, Any] = {
            "id": res.id,
            "type": "rescue" if res.type == "rescue_unit" else res.type,
            "latitude": res.latitude or 12.93,
            "longitude": res.longitude or 77.62,
            "capabilities": list(res.capabilities or []),
            "capacity": res.capacity or 2,
            "status": mapped_status,
        }
        if "name" in defaults:
            res_item["name"] = defaults["name"]
        if live_a is not None:
            res_item["assignedIncident"] = live_a.incident_id
        if eta is not None:
            res_item["eta"] = eta
        if distance_km is not None:
            res_item["distanceKm"] = distance_km
        resources.append(res_item)

    # Current (highest-version) recommendation per incident
    latest_rec_by_incident: dict[str, Recommendation] = {}
    for rec in recommendations_rows:
        if rec.incident_id not in latest_rec_by_incident:
            latest_rec_by_incident[rec.incident_id] = rec

    recommendations: list[dict[str, Any]] = []
    if scenario != "empty_incidents":
        for rec in latest_rec_by_incident.values():
            rec_item: dict[str, Any] = {
                "incident": rec.incident_id,
                "priority_score": rec.priority_score or 94,
                "recommended_resources": list(rec.recommended_resources),
                "reason": rec.reason,
                "approval_required": rec.state == RecommendationState.PENDING,
                "confidence": rec.confidence if rec.confidence is not None else 0.91,
                "version": rec.version,
                "state": rec.state.value,
                "explanation": list(rec.explanation or []),
            }
            if rec.replacement_for_resource_id:
                rec_item["replacementFor"] = rec.replacement_for_resource_id
            recommendations.append(rec_item)

    assignments: list[dict[str, Any]] = []
    for a in assignments_rows:
        if a.status in (AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE):
            a_status = "dispatched"
        elif a.status == AssignmentStatus.COMPLETED:
            a_status = "completed"
        else:
            a_status = "released"
        assignments.append(
            {
                "id": a.id,
                "incidentId": a.incident_id,
                "resourceId": a.resource_id,
                "approvedBy": "coordinator",
                "createdAt": a.assigned_at.isoformat(),
                "status": a_status,
            }
        )

    valid_event_types = {
        "incident_received",
        "duplicates_merged",
        "priority_updated",
        "recommendation_generated",
        "approval_requested",
        "approved",
        "modified",
        "rejected",
        "resource_dispatched",
        "road_block_detected",
        "replanning_started",
        "replacement_recommended",
        "replacement_approved",
        "redispatched",
        "incident_resolved",
    }
    activity: list[dict[str, Any]] = []
    for log_row in actions_rows:
        if log_row.action not in valid_event_types:
            continue
        src = log_row.source if log_row.source in ("intake", "ai", "coordinator", "automation") else "automation"
        meta = dict(log_row.log_metadata or {})
        if log_row.incident_id and "id" not in meta:
            meta["id"] = log_row.incident_id
        if log_row.action == "resource_dispatched" and log_row.resource_id and "resources" not in meta:
            meta["resources"] = log_row.resource_id
            meta["eta"] = FLEET_DEFAULTS.get(log_row.resource_id, {}).get("eta", 0)
        if log_row.action == "road_block_detected":
            meta.setdefault("resources", log_row.resource_id or "AMB-02")
            meta.setdefault("old", meta.get("previous_eta_minutes", 6))
            meta.setdefault("eta", meta.get("eta_minutes", 24))
        if log_row.action == "redispatched":
            meta.setdefault("eta", 9)
        activity.append(
            {
                "id": f"EVT-{log_row.id}",
                "timestamp": log_row.timestamp.isoformat(),
                "source": src,
                "type": log_row.action,
                "title": f"events.{log_row.action}",
                "description": f"eventDescriptions.{log_row.action}",
                "incidentId": log_row.incident_id or "INC-1042",
                "metadata": meta,
            }
        )

    active_incidents = [i for i in incidents if i["status"] not in ("resolved", "rejected")]
    metrics = {
        "criticalIncidents": sum(1 for i in active_incidents if i["severity"] == 5),
        "activeIncidents": len(active_incidents),
        "availableAmbulances": sum(
            1 for r in resources if r["type"] == "ambulance" and r["status"] == "available"
        ),
        "availableRescueTeams": sum(
            1 for r in resources if r["type"] == "rescue" and r["status"] == "available"
        ),
    }

    last_sync = (now - timedelta(minutes=12)) if scenario == "stale" else now
    return {
        "incidents": incidents,
        "resources": resources,
        "recommendations": recommendations,
        "assignments": assignments,
        "activity": activity,
        "metrics": metrics,
        "health": {
            "mode": "backend",
            "automation": "offline" if scenario == "offline" else "n8n",
            "stale": scenario == "stale",
            "lastSync": last_sync.isoformat(),
        },
        "demoIndex": _derive_demo_index(db),
        "scenario": scenario,
        "operationalRevision": current_operational_revision(db),
        "aiEngine": ai_engine_service.get_ai_engine_status(),
    }
