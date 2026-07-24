"""Maintenance business logic (proxying the ERPNext Maintenance Visit DocType)."""

from datetime import date

from fastapi import HTTPException, status

from repositories.maintenance_repository import MaintenanceRepository
from schemas.maintenance import (
    CompleteRequest,
    MaintenanceCreate,
    MaintenanceRead,
    MaintenanceUpdate,
)


class MaintenanceService:
    def __init__(self, repo: MaintenanceRepository) -> None:
        self.repo = repo

    async def list(
        self,
        search: str | None = None,
        status: str | None = None,
        engineer: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[MaintenanceRead]:
        return await self.repo.list(search, status, engineer, limit, start)

    async def get(self, ticket_id: str) -> MaintenanceRead:
        ticket = await self.repo.get(ticket_id)
        if ticket is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
        return ticket

    async def create(self, data: MaintenanceCreate) -> MaintenanceRead:
        return await self.repo.create(data)

    async def update(self, ticket_id: str, data: MaintenanceUpdate) -> MaintenanceRead:
        await self.get(ticket_id)
        return await self.repo.update(
            ticket_id, data.model_dump(exclude_unset=True, exclude_none=True)
        )

    async def delete(self, ticket_id: str) -> None:
        await self.get(ticket_id)
        await self.repo.delete(ticket_id)

    async def complete(self, ticket_id: str, data: CompleteRequest) -> MaintenanceRead:
        ticket = await self.get(ticket_id)
        changes: dict = {
            "status": "Completed",
            "customer_signed": data.signed,
            "visit_date": ticket.visit_date or date.today().isoformat(),
        }
        if data.parts_used:
            changes["parts_used"] = data.parts_used
        return await self.repo.update(ticket_id, changes)
