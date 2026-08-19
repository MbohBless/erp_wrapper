"""Dashboard endpoint. Thin controller — logic lives in DashboardService.

Any authenticated user may open the dashboard, but *what it contains* depends on
their role: see ``services.dashboard_service.VISIBLE_FIELDS``. The route stays
open and the payload narrows, rather than the whole page being denied — a Store
Keeper has a legitimate dashboard, it just is not the finance one.
"""

from fastapi import APIRouter, Depends

from api.deps import get_current_user, get_dashboard_service
from models.user import User
from schemas.dashboard import DashboardSummary
from services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardSummary, response_model_exclude_none=True)
async def get_dashboard(
    service: DashboardService = Depends(get_dashboard_service),
    current_user: User = Depends(get_current_user),
) -> DashboardSummary:
    # exclude_none above means withheld fields are absent from the JSON rather
    # than present as null — nothing to read, and nothing to hint at.
    return await service.get_summary(role=str(current_user.role))
