"""Sales invoice business logic (proxying the ERPNext Sales Invoice DocType)."""

from fastapi import HTTPException, status

from repositories.sales_repository import SalesRepository
from schemas.sales import SalesInvoiceCreate, SalesInvoiceRead, SalesInvoiceUpdate


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

    async def update(self, invoice_id: str, data: SalesInvoiceUpdate) -> SalesInvoiceRead:
        """Correct a posted invoice.

        There is no in-place edit: the invoice is cancelled and a corrected copy
        posted in its place, under a new number ("<original>-1"). The caller
        needs to know that, which is why the route is documented as an amend
        rather than an update.
        """
        current = await self.get(invoice_id)  # 404s if there is no such invoice
        self._ensure_amendable(current)
        return await self.repo.amend(invoice_id, data)

    @staticmethod
    def _ensure_amendable(invoice: SalesInvoiceRead) -> None:
        """Refuse, before anything is cancelled, what ERPNext would refuse after.

        The cancel and the re-post are two calls, not one transaction. Letting
        ERPNext be the one to say no means it says so *after* the original has
        already been reversed — and it says it as an opaque 502. Both of the
        cases below are ones a user hits by accident, so they are worth naming.
        """
        if invoice.is_opening:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{invoice.id} is an opening balance from the first-time books "
                "setup, not a sale. Editing it would leave the opening balances "
                "out of step with the ledger.",
            )
        # ERPNext zeroes `outstanding_amount` when it cancels, so on an already
        # cancelled invoice this comparison would read as fully paid and refuse
        # the retry that is the whole point of the resume path.
        received = invoice.grand_total - invoice.outstanding_amount
        if received > 0.005 and not invoice.is_cancelled:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{invoice.id} already has {received:,.0f} XAF received against "
                "it, so it cannot be cancelled. Cancel the payment first, or "
                "raise a credit note instead of editing the invoice.",
            )
