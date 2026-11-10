"""Interactive backend demo endpoints for the opt-in live dashboard and n8n bridge."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_coordinator, verify_any_api_key
from app.core.config import Settings, get_settings
from app.services import ai_engine_service, demo_scenario_service

router = APIRouter(prefix="/integration/v1/demo", tags=["demo-integration"])


class DemoResetRequest(BaseModel):
    for_run: bool = False
    model_config = ConfigDict(extra="forbid")


class DemoScenarioRequest(BaseModel):
    scenario: str = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


class DemoStepRequest(BaseModel):
    step: str = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


class DemoApproveRequest(BaseModel):
    version: int = Field(gt=0)
    model_config = ConfigDict(extra="forbid")


class DemoModifyRequest(BaseModel):
    version: int = Field(gt=0)
    recommended_resources: list[str] = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


class DemoRejectRequest(BaseModel):
    version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)
    model_config = ConfigDict(extra="forbid")


class DemoAssignmentRequest(BaseModel):
    incident_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")


class DemoTranslateRequest(BaseModel):
    id: str = Field(min_length=1)
    originalText: str = Field(min_length=1)
    originalLanguage: str = Field(min_length=2, max_length=5)
    targetLanguage: str = Field(min_length=2, max_length=5)
    receivedAt: str | None = None
    model_config = ConfigDict(extra="forbid")


class N8nSyncRequest(BaseModel):
    workflow: str = Field(min_length=1)
    idempotency_key: str | None = None
    model_config = ConfigDict(extra="forbid")


def _resolve_actor(
    request: Request,
    settings: Settings,
    x_api_key: str | None,
    x_fixture_actor: str | None,
) -> str:
    """Determines whether the caller is an authenticated human coordinator or automation."""
    if x_fixture_actor == "automation":
        return "automation"
    if not settings.auth_enabled:
        return "coordinator"
    expected_coord = settings.effective_coordinator_key
    if expected_coord and x_api_key and secrets.compare_digest(x_api_key, expected_coord):
        return "coordinator"
    return "automation"


@router.get(
    "/snapshot",
    summary="Get the full interactive dashboard snapshot from PostgreSQL",
    dependencies=[Depends(verify_any_api_key)],
)
def get_demo_snapshot(db: Session = Depends(get_db)) -> dict[str, Any]:
    return demo_scenario_service.get_demo_dashboard_snapshot(db)


@router.post(
    "/reset",
    summary="Reset and reseed the PostgreSQL demo scenario",
    dependencies=[Depends(verify_any_api_key)],
)
def reset_demo(
    payload: DemoResetRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return demo_scenario_service.reset_demo_database(db, for_run=payload.for_run)


@router.post(
    "/scenario",
    summary="Switch the active operational scenario (normal, stale, offline, etc.)",
    dependencies=[Depends(verify_any_api_key)],
)
def set_demo_scenario(
    payload: DemoScenarioRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return demo_scenario_service.set_demo_scenario(db, payload.scenario)


@router.post(
    "/step",
    summary="Execute one step of the canonical INC-1042 emergency lifecycle",
    dependencies=[Depends(verify_any_api_key)],
)
def execute_demo_step(
    payload: DemoStepRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_fixture_actor: str | None = Header(default=None, alias="X-Fixture-Actor"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    actor = _resolve_actor(request, settings, x_api_key, x_fixture_actor)
    if payload.step in ("approve", "approveReplacement") and actor != "coordinator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recommendation approval requires a human coordinator API key and cannot be performed by AI or n8n automation.",
        )
    return demo_scenario_service.execute_demo_step(
        db,
        payload.step,
        actor=actor,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/incidents/{incident_id}/approve",
    summary="Approve the current pending recommendation in the demo scenario",
)
def approve_demo_recommendation(
    incident_id: str,
    payload: DemoApproveRequest,
    db: Session = Depends(get_db),
    approved_by: str = Depends(require_coordinator),
) -> dict[str, Any]:
    return demo_scenario_service.approve_demo_recommendation(
        db, incident_id, payload.version, approved_by=approved_by
    )


@router.post(
    "/incidents/{incident_id}/modify",
    summary="Modify the current pending recommendation in the demo scenario",
)
def modify_demo_recommendation(
    incident_id: str,
    payload: DemoModifyRequest,
    db: Session = Depends(get_db),
    modified_by: str = Depends(require_coordinator),
) -> dict[str, Any]:
    return demo_scenario_service.modify_demo_recommendation(
        db,
        incident_id,
        payload.recommended_resources,
        payload.version,
        modified_by=modified_by,
    )


@router.post(
    "/incidents/{incident_id}/reject",
    summary="Reject the current pending recommendation in the demo scenario",
)
def reject_demo_recommendation(
    incident_id: str,
    payload: DemoRejectRequest,
    db: Session = Depends(get_db),
    rejected_by: str = Depends(require_coordinator),
) -> dict[str, Any]:
    return demo_scenario_service.reject_demo_recommendation(
        db,
        incident_id,
        payload.reason,
        payload.version,
        rejected_by=rejected_by,
    )


@router.post(
    "/assignments",
    summary="Idempotently confirm or retrieve a live assignment for an approved plan",
    dependencies=[Depends(verify_any_api_key)],
)
def create_demo_assignment(
    payload: DemoAssignmentRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return demo_scenario_service.create_demo_assignment(
        db, payload.incident_id, payload.resource_id
    )


@router.post(
    "/translate",
    summary="Translate an emergency report through the AI engine contract",
    dependencies=[Depends(verify_any_api_key)],
)
def translate_demo_report(payload: DemoTranslateRequest) -> dict[str, Any]:
    result = ai_engine_service.translate_report_with_ai(
        original_text=payload.originalText,
        original_language=payload.originalLanguage,
        target_language=payload.targetLanguage,
    )
    return {
        "id": payload.id,
        "originalText": payload.originalText,
        "originalLanguage": payload.originalLanguage,
        "receivedAt": payload.receivedAt or "",
        "translatedText": result["translated_text"],
        "translatedLanguage": payload.targetLanguage,
    }


@router.post(
    "/n8n-sync",
    summary="Synchronize an n8n fixture workflow stage with the PostgreSQL demo scenario",
    dependencies=[Depends(verify_any_api_key)],
)
def sync_n8n_workflow(
    payload: N8nSyncRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_fixture_actor: str | None = Header(default=None, alias="X-Fixture-Actor"),
) -> dict[str, Any]:
    """Bridges the 4 n8n fixture workflows (`intake`, `dispatch`, `replan`, `resolution`)
    and operator approval to the PostgreSQL demo scenario idempotently.
    """
    actor = _resolve_actor(request, settings, x_api_key, x_fixture_actor)
    wf = payload.workflow

    if wf == "reset":
        return demo_scenario_service.reset_demo_database(db, for_run=True)

    snapshot = demo_scenario_service.get_demo_dashboard_snapshot(db)
    idx = snapshot["demoIndex"]

    if wf == "intake":
        # Runs steps 0..4 (receive -> merge -> priority -> recommend -> request) idempotently
        if idx == 0:
            for step_name in ("receive", "merge", "priority", "recommend", "request"):
                snapshot = demo_scenario_service.execute_demo_step(
                    db, step_name, actor="automation"
                )
        return snapshot

    if wf in ("operator_approve", "approve"):
        if actor != "coordinator":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operator approval requires coordinator credentials; n8n automation cannot approve.",
            )
        if idx == 5:
            return demo_scenario_service.execute_demo_step(db, "approve", actor="coordinator")
        if idx == 9:
            return demo_scenario_service.execute_demo_step(
                db, "approveReplacement", actor="coordinator"
            )
        return snapshot

    if wf == "dispatch":
        # Dispatch workflow verifies that coordinator approval has already taken place
        if idx < 6:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot execute dispatch workflow before human coordinator approval.",
            )
        return snapshot

    if wf == "replan":
        # Runs steps 6..8 (block -> replan -> replace) idempotently, stopping at awaiting_replacement (idx 9)
        if idx == 6:
            for step_name in ("block", "replan", "replace"):
                snapshot = demo_scenario_service.execute_demo_step(
                    db, step_name, actor="automation"
                )
        return snapshot

    if wf == "resolution":
        if idx == 10:
            snapshot = demo_scenario_service.execute_demo_step(
                db, "resolve", actor="automation"
            )
        return snapshot

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Unknown n8n workflow sync stage '{wf}'.",
    )
