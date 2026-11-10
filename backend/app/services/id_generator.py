"""Generates human-readable entity IDs (INC-1042, AMB-02, ASG-887, ...).

Uses native PostgreSQL sequences via nextval(), which is atomic under
concurrency without any application-level locking.

Incidents and assignments use one fixed sequence each (created in the first
Alembic migration). Resources use one sequence per ID prefix, created
on demand with CREATE SEQUENCE IF NOT EXISTS the first time a given
resource type is seen — this is what keeps resource types extensible
without requiring a migration every time a new type is introduced.
"""

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.domain_values import RESOURCE_TYPE_PREFIXES

_INCIDENT_SEQUENCE = "incident_seq"
_ASSIGNMENT_SEQUENCE = "assignment_seq"
_REPORT_SEQUENCE = "report_seq"
_RECOMMENDATION_SEQUENCE = "recommendation_seq"


def resource_prefix_for_type(resource_type: str) -> str:
    """Returns the ID prefix for a resource type.

    Known demo types map to a friendly prefix (ambulance -> AMB). Any other
    type still gets a stable, readable prefix derived from its own name, so
    a brand new resource type works without touching this file.
    """
    normalized = resource_type.strip().lower()
    if normalized in RESOURCE_TYPE_PREFIXES:
        return RESOURCE_TYPE_PREFIXES[normalized]

    alnum_only = re.sub(r"[^A-Za-z0-9]", "", normalized).upper()
    return alnum_only[:8] or "RES"


def next_incident_id(db: Session) -> str:
    value = db.execute(text(f"SELECT nextval('{_INCIDENT_SEQUENCE}')")).scalar_one()
    return f"INC-{value:02d}"


def next_assignment_id(db: Session) -> str:
    value = db.execute(text(f"SELECT nextval('{_ASSIGNMENT_SEQUENCE}')")).scalar_one()
    return f"ASG-{value:02d}"


def next_report_id(db: Session) -> str:
    value = db.execute(text(f"SELECT nextval('{_REPORT_SEQUENCE}')")).scalar_one()
    return f"RPT-{value:02d}"


def next_recommendation_id(db: Session) -> str:
    value = db.execute(
        text(f"SELECT nextval('{_RECOMMENDATION_SEQUENCE}')")
    ).scalar_one()
    return f"REC-{value:02d}"


def next_resource_id(db: Session, resource_type: str) -> str:
    prefix = resource_prefix_for_type(resource_type)
    # `prefix` is guaranteed to be [A-Z0-9]+ by resource_prefix_for_type,
    # so building the sequence name/identifier this way is not injectable.
    sequence_name = f"resource_seq_{prefix.lower()}"
    db.execute(text(f'CREATE SEQUENCE IF NOT EXISTS "{sequence_name}"'))
    value = db.execute(text(f"SELECT nextval('\"{sequence_name}\"')")).scalar_one()
    return f"{prefix}-{value:02d}"
