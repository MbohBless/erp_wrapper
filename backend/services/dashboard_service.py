"""Dashboard business logic."""

from datetime import date

from repositories.dashboard_repository import DashboardRepository
from schemas.dashboard import DashboardSummary


class DashboardService:
    def __init__(self, repo: DashboardRepository) -> None:
        self.repo = repo

    async def get_summary(self) -> DashboardSummary:
        return await self.repo.get_summary(date.today())
