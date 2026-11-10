from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health check",
    description=(
        "Reports service status and verifies the PostgreSQL connection. "
        "n8n and infra probes should poll this endpoint."
    ),
)
def health_check(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # surfaced, never silently swallowed
        db_status = f"error: {exc}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "environment": settings.app_env,
        "database": db_status,
    }
