"""Supplier management business logic (proxying the ERPNext Supplier DocType)."""

from fastapi import HTTPException, status

from repositories.supplier_repository import SupplierRepository
from schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate


class SupplierService:
    def __init__(self, repo: SupplierRepository) -> None:
        self.repo = repo

    async def list(
        self,
        search: str | None = None,
        supplier_type: str | None = None,
        group: str | None = None,
        disabled: bool | None = None,
        limit: int = 20,
        start: int = 0,
    ) -> list[SupplierRead]:
        return await self.repo.list(search, supplier_type, group, disabled, limit, start)

    async def get(self, name: str) -> SupplierRead:
        supplier = await self.repo.get(name)
        if supplier is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
        return supplier

    async def create(self, data: SupplierCreate) -> SupplierRead:
        if await self.repo.get(data.name) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Supplier already exists")
        return await self.repo.create(data)

    async def update(self, name: str, data: SupplierUpdate) -> SupplierRead:
        await self.get(name)  # 404 if missing
        return await self.repo.update(name, data)

    async def delete(self, name: str) -> None:
        await self.get(name)  # 404 if missing
        await self.repo.delete(name)
