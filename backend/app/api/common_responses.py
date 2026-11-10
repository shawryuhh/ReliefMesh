"""Reusable OpenAPI `responses=` fragments for the domain error shapes.

These document what routes.deps + main.py's exception handlers actually do
at runtime (app/core/exceptions.py -> main.py) — they don't change behavior,
they just make the generated OpenAPI schema/Swagger UI show integrators
(frontend, AI service, n8n) the error shape to expect for each status code
without having to read the service code.
"""

from app.schemas.errors import ErrorResponse

NOT_FOUND = {404: {"model": ErrorResponse, "description": "The referenced entity does not exist."}}

CONFLICT = {
    409: {
        "model": ErrorResponse,
        "description": "The request conflicts with the current state of the data (e.g. an "
        "invalid state transition, or a resource that is no longer available).",
    }
}

VALIDATION_FAILED = {
    422: {
        "model": ErrorResponse,
        "description": "The request is well-formed but semantically invalid (business-rule "
        "validation, as opposed to a schema/type error).",
    }
}


def responses(*fragments: dict) -> dict:
    """Merges response fragments, e.g. responses(NOT_FOUND, CONFLICT)."""
    merged: dict = {}
    for fragment in fragments:
        merged.update(fragment)
    return merged
