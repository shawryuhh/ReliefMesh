"""Domain exceptions raised by the service layer.

Route handlers never construct HTTPException directly for business errors —
they let these propagate and a single set of handlers (registered in main.py)
translates them into consistent JSON error responses.
"""


class DomainError(Exception):
    """Base class for all business-rule errors raised by the service layer.

    `code` is an optional, stable machine-readable string (e.g. "STALE_PLAN")
    for callers that need to branch on the failure reason instead of parsing
    `message`. Existing raises that don't pass one keep getting `code: null`
    in the response — this is purely additive.
    """

    def __init__(self, message: str, code: str | None = None) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(DomainError):
    """Raised when a referenced entity does not exist."""


class ConflictError(DomainError):
    """Raised when an operation cannot proceed due to the current state of the data
    (e.g. a resource is already assigned, or a state transition is disallowed)."""


class ValidationFailedError(DomainError):
    """Raised for business-rule validation failures that aren't caught by Pydantic
    (e.g. a well-formed but semantically invalid request)."""


class StaleRecommendationError(ConflictError):
    """The recommendation being approved is no longer the current pending one —
    already decided, or a newer version exists (code=STALE_PLAN)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STALE_PLAN")


class ResourceUnavailableError(ConflictError):
    """One or more resources in the recommendation are no longer AVAILABLE
    (code=RESOURCE_UNAVAILABLE)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="RESOURCE_UNAVAILABLE")


class PendingPlanExistsError(ConflictError):
    """A new plan can't be submitted while the incident still has a PENDING
    one awaiting a coordinator decision (code=PENDING_PLAN_EXISTS)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="PENDING_PLAN_EXISTS")


class IdempotencyConflictError(ConflictError):
    """An analysis_revision already used for this incident was resent with a
    different plan — a retry must resend the same payload
    (code=IDEMPOTENCY_CONFLICT)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="IDEMPOTENCY_CONFLICT")


class ResourceNotAssignedError(ConflictError):
    """The resource a disruption/replacement refers to has no live
    assignment on the incident (code=RESOURCE_NOT_ASSIGNED)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="RESOURCE_NOT_ASSIGNED")


class InvalidResourcesError(ValidationFailedError):
    """A submitted resource list is semantically invalid — duplicates, or a
    replacement plan that still includes the failed resource
    (code=INVALID_RESOURCES)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="INVALID_RESOURCES")


class ApprovalRequiredError(ConflictError):
    """Raised by POST /assignments when the requested dispatch isn't backed
    by a valid, current, APPROVED recommendation covering the requested
    resource(s) — the direct-dispatch bypass this guards against
    (code=APPROVAL_REQUIRED)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="APPROVAL_REQUIRED")
