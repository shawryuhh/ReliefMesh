"""Model-level tests for the `reports` table added in migration
0f0c42fad357. No report intake API exists yet (that's Phase 3), so these
write directly through SQLAlchemy, the same way the initial migration's
race-condition tests exercise the database layer directly.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.incident import Incident
from app.models.report import Report
from app.services.id_generator import next_report_id


def _create_incident(client, location="Test Location"):
    response = client.post(
        "/incidents",
        json={"location": location, "type": "flood", "severity": "CRITICAL"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_report_persists_and_round_trips(client):
    incident_id = _create_incident(client)
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        report_id = next_report_id(db)
        report = Report(
            id=report_id,
            incident_id=incident_id,
            source_report_id="demo-run-01-report-01",
            producer_identity="n8n",
            channel="whatsapp",
            original_text="Water entering Krishna Apartments Block C.",
            original_language="en",
            received_at=now,
        )
        db.add(report)
        db.commit()

    with SessionLocal() as db:
        fetched = db.get(Report, report_id)
        assert fetched is not None
        assert fetched.incident_id == incident_id
        assert fetched.original_text == "Water entering Krishna Apartments Block C."
        assert fetched.original_language == "en"
        assert fetched.translated_text is None
        assert fetched.translated_language is None


def test_report_incident_defaults_to_received_phase(client):
    incident_id = _create_incident(client)

    with SessionLocal() as db:
        incident = db.get(Incident, incident_id)
        assert incident.operational_phase.value == "received"
        assert incident.severity_score is None
        assert incident.vulnerabilities == []
        assert incident.duplicate_count == 0


def test_duplicate_source_report_id_from_same_producer_rejected(client):
    incident_id = _create_incident(client)
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        db.add(Report(
            id=next_report_id(db), incident_id=incident_id,
            source_report_id="demo-run-01-report-02", producer_identity="n8n",
            original_text="First delivery", original_language="en", received_at=now,
        ))
        db.commit()

    with SessionLocal() as db:
        db.add(Report(
            id=next_report_id(db), incident_id=incident_id,
            source_report_id="demo-run-01-report-02", producer_identity="n8n",
            original_text="Retried delivery, same event id", original_language="en",
            received_at=now,
        ))
        with pytest.raises(IntegrityError):
            db.commit()


def test_reports_without_source_id_are_unconstrained(client):
    incident_id = _create_incident(client)
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        db.add(Report(
            id=next_report_id(db), incident_id=incident_id,
            original_text="Corroborating report A", original_language="en", received_at=now,
        ))
        db.add(Report(
            id=next_report_id(db), incident_id=incident_id,
            original_text="Corroborating report B", original_language="en", received_at=now,
        ))
        db.commit()

    with SessionLocal() as db:
        count = db.query(Report).filter(Report.incident_id == incident_id).count()
        assert count == 2
