"""Fixed state-machine enums.

Unlike `type` fields (see app.core.domain_values), these represent genuine
finite state machines with explicitly allowed transitions enforced in the
service layer (see app/services/*_service.py). They are intentionally rigid.
"""

from enum import Enum


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class ResourceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DISPATCHED = "DISPATCHED"
    ACTIVE = "ACTIVE"
    UNAVAILABLE = "UNAVAILABLE"


class AssignmentStatus(str, Enum):
    ASSIGNED = "ASSIGNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


class OperationalPhase(str, Enum):
    """Frontend-facing lifecycle phase, persisted alongside (not instead of)
    the broad `IncidentStatus` above. Values are exact lowercase strings
    from the frontend's `IncidentStatus` union (see
    TEAM_INTEGRATION_PLAN.md D2 and frontend/types/index.ts) so the API
    layer never has to re-case or translate them.
    """

    RECEIVED = "received"
    ANALYZING = "analyzing"
    PRIORITIZED = "prioritized"
    RECOMMENDED = "recommended"
    AWAITING_APPROVAL = "awaiting_approval"
    DISPATCHED = "dispatched"
    BLOCKED = "blocked"
    REPLANNING = "replanning"
    AWAITING_REPLACEMENT = "awaiting_replacement"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class RecommendationState(str, Enum):
    """Matches the frontend `Recommendation.state` union exactly (see
    TEAM_INTEGRATION_PLAN.md D4 and frontend/types/index.ts)."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
