"""Sales invoice business logic (proxying the ERPNext Sales Invoice DocType)."""

from fastapi import HTTPException, status

from repositories.sales_repository import SalesRepository
from schemas.sales import SalesInvoiceCreate, SalesInvoiceRead


class SalesService:
    def __init__(self, repo: SalesRepository) -> None:
        self.repo = repo

    async def list(
        self,
        search: str | None = None,
        status: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[SalesInvoiceRead]:
        return await self.repo.list(search, status, limit, start)

    async def get(self, invoice_id: str) -> SalesInvoiceRead:
        invoice = await self.repo.get(invoice_id)
        if invoice is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
        return invoice

    async def create(self, data: SalesInvoiceCreate) -> SalesInvoiceRead:
        return await self.repo.create(data)
