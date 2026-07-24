"""Equipment business logic (proxying the ERPNext Serial No DocType)."""

from datetime import date

from fastapi import HTTPException, status

from repositories.equipment_repository import EquipmentRepository
from schemas.equipment import (
    EquipmentCreate,
    EquipmentRead,
    EquipmentUpdate,
    InstallRequest,
)


class EquipmentService:
    def __init__(self, repo: EquipmentRepository) -> None:
        self.repo = repo

    async def list(
        self,
        search: str | None = None,
        status: str | None = None,
        customer: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[EquipmentRead]:
        return await self.repo.list(search, status, customer, limit, start)

    async def get(self, equipment_id: str) -> EquipmentRead:
        equipment = await self.repo.get(equipment_id)
        if equipment is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipment not found")
        return equipment

    async def create(self, data: EquipmentCreate) -> EquipmentRead:
        if await self.repo.get(data.serial_no) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Equipment already exists")
        return await self.repo.create(data)

    async def update(self, equipment_id: str, data: EquipmentUpdate) -> EquipmentRead:
        await self.get(equipment_id)
        return await self.repo.update(
            equipment_id, data.model_dump(exclude_unset=True, exclude_none=True)
        )

    async def delete(self, equipment_id: str) -> None:
        await self.get(equipment_id)
        await self.repo.delete(equipment_id)

    async def install(self, equipment_id: str, data: InstallRequest) -> EquipmentRead:
        await self.get(equipment_id)
        changes: dict = {
            "installation_date": data.installation_date or date.today().isoformat(),
            "status": "Installed",
        }
        if data.customer:
            changes["customer"] = data.customer
        return await self.repo.update(equipment_id, changes)
