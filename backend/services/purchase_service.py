"""Purchase invoice business logic (proxying the ERPNext Purchase Invoice DocType)."""

from fastapi import HTTPException, status

from repositories.purchase_repository import PurchaseRepository
from schemas.purchases import PurchaseInvoiceCreate, PurchaseInvoiceRead


class PurchaseService:
    def __init__(self, repo: PurchaseRepository) -> None:
        self.repo = repo

    async def list(
        self,
        search: str | None = None,
        status: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[PurchaseInvoiceRead]:
        return await self.repo.list(search, status, limit, start)

    async def get(self, bill_id: str) -> PurchaseInvoiceRead:
        bill = await self.repo.get(bill_id)
        if bill is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase not found")
        return bill

    async def create(self, data: PurchaseInvoiceCreate) -> PurchaseInvoiceRead:
        return await self.repo.create(data)
