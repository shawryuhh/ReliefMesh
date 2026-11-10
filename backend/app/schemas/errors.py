from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Shape of every error response in this API.

    Every domain error (see app.core.exceptions) is translated by the
    handlers in main.py into this exact shape, regardless of which endpoint
    raised it — integrators can rely on `detail` always being a
    human-readable string, never a nested object.
    """

    detail: str
    code: str | None = None

    model_config = {"json_schema_extra": {"example": {"detail": "Incident 'INC-9999' not found.", "code": None}}}
