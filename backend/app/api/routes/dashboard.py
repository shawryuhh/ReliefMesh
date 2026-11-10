from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.schemas.dashboard import DashboardResponse
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"], dependencies=[Depends(verify_api_key)])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Frontend command-center summary",
    description="Aggregated, read-only snapshot for the dashboard: incident/resource counts, "
    "live assignment count, recent activity, and current incidents/resources. Computed live "
    "from the same tables the rest of the API uses — nothing here is separately stored state.",
)
def get_dashboard(
    activity_limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    return dashboard_service.get_dashboard(db, activity_limit=activity_limit)
