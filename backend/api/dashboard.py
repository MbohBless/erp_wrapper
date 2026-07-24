"""Dashboard endpoint. Thin controller — logic lives in DashboardService.

Any authenticated user may view the dashboard (cards are role-agnostic in V1).
"""

from fastapi import APIRouter, Depends

from api.deps import get_current_user, get_dashboard_service
from schemas.dashboard import DashboardSummary
from services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "", response_model=DashboardSummary, dependencies=[Depends(get_current_user)]
)
async def get_dashboard(
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardSummary:
    return await service.get_summary()
