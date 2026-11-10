"""Explicit state transition tables for incidents, resources and assignments.

A transition is only allowed if it appears in the relevant map below. This is
the single place these rules are defined — services call
`assert_transition_allowed` instead of hand-rolling if/else chains, so the
rules can't drift out of sync between endpoints.
"""

from app.core.exceptions import ConflictError, StaleRecommendationError
from app.models.enums import AssignmentStatus, IncidentStatus, OperationalPhase, ResourceStatus

ALLOWED_RESOURCE_TRANSITIONS: dict[ResourceStatus, set[ResourceStatus]] = {
    ResourceStatus.AVAILABLE: {ResourceStatus.DISPATCHED, ResourceStatus.UNAVAILABLE},
    ResourceStatus.DISPATCHED: {
        ResourceStatus.ACTIVE,
        ResourceStatus.AVAILABLE,
        ResourceStatus.UNAVAILABLE,
    },
    ResourceStatus.ACTIVE: {ResourceStatus.AVAILABLE, ResourceStatus.UNAVAILABLE},
    ResourceStatus.UNAVAILABLE: {ResourceStatus.AVAILABLE},
}

ALLOWED_INCIDENT_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.UNASSIGNED: {IncidentStatus.ASSIGNED, IncidentStatus.CANCELLED},
    IncidentStatus.ASSIGNED: {
        IncidentStatus.ACTIVE,
        IncidentStatus.RESOLVED,
        IncidentStatus.UNASSIGNED,
        IncidentStatus.CANCELLED,
    },
    IncidentStatus.ACTIVE: {IncidentStatus.RESOLVED, IncidentStatus.CANCELLED},
    IncidentStatus.RESOLVED: set(),
    IncidentStatus.CANCELLED: set(),
}

ALLOWED_ASSIGNMENT_TRANSITIONS: dict[AssignmentStatus, set[AssignmentStatus]] = {
    AssignmentStatus.ASSIGNED: {
        AssignmentStatus.ACTIVE,
        AssignmentStatus.CANCELLED,
        AssignmentStatus.SUPERSEDED,
    },
    AssignmentStatus.ACTIVE: {
        AssignmentStatus.COMPLETED,
        AssignmentStatus.CANCELLED,
        AssignmentStatus.SUPERSEDED,
    },
    AssignmentStatus.COMPLETED: set(),
    AssignmentStatus.CANCELLED: set(),
    AssignmentStatus.SUPERSEDED: set(),
}


# Operational phases (the frontend-facing lifecycle) each plan/disruption
# action may start from, mirroring the frontend mock service: a plan can only
# be approved while the incident awaits that kind of approval, and a
# replacement can only be proposed once an obstruction has blocked it. Unlike
# the status maps above this is keyed by action, not by target phase, since
# the same target (e.g. DISPATCHED) is reached from different actions.
PHASES_ALLOWING_ACTION: dict[str, set[OperationalPhase]] = {
    "submit_recommendation": {
        OperationalPhase.RECEIVED,
        OperationalPhase.ANALYZING,
        OperationalPhase.PRIORITIZED,
        OperationalPhase.RECOMMENDED,
    },
    "approve_recommendation": {OperationalPhase.AWAITING_APPROVAL},
    "modify_recommendation": {
        OperationalPhase.AWAITING_APPROVAL,
        OperationalPhase.AWAITING_REPLACEMENT,
    },
    "reject_recommendation": {
        OperationalPhase.AWAITING_APPROVAL,
        OperationalPhase.AWAITING_REPLACEMENT,
    },
    "report_disruption": {OperationalPhase.DISPATCHED, OperationalPhase.BLOCKED},
    "propose_replacement": {OperationalPhase.BLOCKED, OperationalPhase.REPLANNING},
    "approve_replacement": {OperationalPhase.AWAITING_REPLACEMENT},
}


def assert_phase_allows(incident_id: str, phase: OperationalPhase, action: str) -> None:
    """Wrong-phase failures use STALE_PLAN, matching the frontend contract's
    `error.stalePlan` for an incompatible incident phase."""
    if phase not in PHASES_ALLOWING_ACTION[action]:
        raise StaleRecommendationError(
            f"Incident '{incident_id}' is in phase '{phase.value}'; cannot {action.replace('_', ' ')}."
        )


def assert_transition_allowed(
    entity_name: str,
    current: object,
    target: object,
    allowed_map: dict,
) -> None:
    if current == target:
        raise ConflictError(f"{entity_name} is already in status {current}.")
    allowed = allowed_map.get(current, set())
    if target not in allowed:
        raise ConflictError(
            f"Cannot transition {entity_name} from {current} to {target}."
        )
