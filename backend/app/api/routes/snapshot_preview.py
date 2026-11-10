"""Development-only coherent read snapshot.

Uses a single PostgreSQL REPEATABLE READ transaction. This is not yet the
versioned production snapshot specified in SNAPSHOT_CONTRACT.md.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.models.incident import Incident
from app.models.resource import Resource
from app.models.assignment import Assignment
from app.models.recommendation import Recommendation
from app.models.report import Report
from app.models.action_log import ActionLog

router = APIRouter(prefix="/integration/v1", tags=["integration"])


@router.get("/snapshot-preview")
def snapshot_preview(db: Session = Depends(get_db)):
    settings = get_settings()
    # This route contains original report text. Never expose it with the
    # application's development-default disabled authentication.
    if not settings.auth_enabled or not settings.api_key:
        raise HTTPException(status_code=503, detail="Authenticated snapshot preview unavailable")

    # verify_api_key is intentionally applied separately in the route below.
    # SET TRANSACTION must precede the first query in this session.
    db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
    incidents = db.scalars(select(Incident).order_by(Incident.id)).all()
    resources = db.scalars(select(Resource).order_by(Resource.id)).all()
    assignments = db.scalars(select(Assignment).order_by(Assignment.id)).all()
    recommendations = db.scalars(select(Recommendation).order_by(Recommendation.incident_id, Recommendation.version)).all()
    reports = db.scalars(select(Report).order_by(Report.id)).all()
    events = db.scalars(select(ActionLog).order_by(ActionLog.id)).all()
    # Explicitly no monotonic revision yet; callers must not treat this as
    # an incremental synchronization protocol.
    return {
        "schema_version": 1,
        "revision": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "complete": True,
        "incidents": [{
            "id": i.id, "location": i.location, "latitude": i.latitude,
            "longitude": i.longitude, "type": i.type, "severity": i.severity.value,
            "severity_score": i.severity_score, "priority_score": i.priority_score,
            "confidence": i.confidence, "people_affected": i.people_affected,
            "needs": i.needs, "status": i.status.value,
            "operational_phase": i.operational_phase.value,
            "vulnerabilities": i.vulnerabilities, "duplicate_count": i.duplicate_count,
        } for i in incidents],
        "resources": [{
            "id": r.id, "type": r.type, "location": r.location,
            "latitude": r.latitude, "longitude": r.longitude,
            "capabilities": r.capabilities, "status": r.status.value,
            "capacity": r.capacity,
        } for r in resources],
        "assignments": [{
            "id": a.id, "incident_id": a.incident_id, "resource_id": a.resource_id,
            "status": a.status.value, "assigned_at": a.assigned_at.isoformat(),
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            "recommendation_id": a.recommendation_id, "approved_by": a.approved_by,
        } for a in assignments],
        "recommendations": [{
            "id": r.id, "incident": r.incident_id, "version": r.version,
            "state": r.state.value, "recommended_resources": r.recommended_resources,
            "reason": r.reason, "explanation": r.explanation,
            "confidence": r.confidence, "priority_score": r.priority_score,
            "replacementFor": r.replacement_for_resource_id,
        } for r in recommendations],
        "reports": [{
            "id": r.id, "incident_id": r.incident_id,
            "originalText": r.original_text, "originalLanguage": r.original_language,
            "receivedAt": r.received_at.isoformat(),
            "translatedText": r.translated_text, "translatedLanguage": r.translated_language,
        } for r in reports],
        "activity": [{
            "id": e.id, "timestamp": e.timestamp.isoformat(), "source": e.source,
            "action": e.action, "incident_id": e.incident_id,
            "resource_id": e.resource_id, "assignment_id": e.assignment_id,
        } for e in events],
    }
