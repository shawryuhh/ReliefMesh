from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    activity_log,
    assignments,
    dashboard,
    disruptions,
    health,
    incidents,
    recommendations,
    resources,
    snapshot_preview,
)
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError

settings = get_settings()

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Liveness/readiness probe for infra and n8n polling.",
    },
    {
        "name": "incidents",
        "description": "Incidents reported by ingestion/AI and tracked through to resolution. "
        "The backend never creates or classifies an incident itself — it only records the "
        "decision it's given.",
    },
    {
        "name": "resources",
        "description": "Ambulances, rescue units, shelters, hospitals, volunteers — anything "
        "that can be assigned to an incident.",
    },
    {
        "name": "assignments",
        "description": "Links a resource to an incident. Concurrency-safe: a resource can "
        "never be assigned twice at once, enforced by row locking and a database constraint.",
    },
    {
        "name": "recommendations",
        "description": "AI-proposed resource plans awaiting human approval. Approval is the "
        "only path to recommendation-driven dispatch — it atomically approves the plan, "
        "creates the resulting assignments, and updates incident/resource state together. "
        "Replacement plans for blocked incidents go through the same gate.",
    },
    {
        "name": "disruptions",
        "description": "Reports that a dispatched responder is obstructed (e.g. a road block). "
        "Records the revised ETA and blocks the incident; never releases or reassigns anything.",
    },
    {
        "name": "activity-log",
        "description": "Append-only audit trail. Every state-changing call elsewhere logs its "
        "own entry automatically; this API only adds entries that don't map to one of those, "
        "and reads history back.",
    },
    {
        "name": "dashboard",
        "description": "Read-only, frontend-ready aggregated snapshot, computed live from the "
        "same tables the rest of the API uses.",
    },
]

app = FastAPI(
    title="ReliefMesh Backend",
    description=(
        "System of record for incidents, resources, assignments and audit logs in the "
        "ReliefMesh crisis coordination platform.\n\n"
        "This service owns state and enforces safety/consistency rules (locking, state "
        "machines, atomic transactions); it does not do any AI reasoning, deduplication, or "
        "priority scoring itself — it only validates and persists decisions handed to it by "
        "the AI service / n8n / a human dispatcher.\n\n"
        "See the repository README for setup, an integration walkthrough for n8n/AI "
        "payloads, and the canonical demo scenario."
    ),
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NotFoundError)
def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(ConflictError)
def handle_conflict(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(ValidationFailedError)
def handle_validation_failed(request: Request, exc: ValidationFailedError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message, "code": exc.code})


app.include_router(health.router)
app.include_router(incidents.router)
app.include_router(resources.router)
app.include_router(assignments.router)
app.include_router(recommendations.router)
app.include_router(activity_log.router)
app.include_router(dashboard.router)
app.include_router(disruptions.router)

# Authenticated read-only development snapshot; not a production sync API.
app.include_router(snapshot_preview.router)
