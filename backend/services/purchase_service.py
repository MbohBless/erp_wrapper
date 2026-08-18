"""Purchase invoice business logic (proxying the ERPNext Purchase Invoice DocType)."""

from fastapi import HTTPException, status

from repositories.purchase_repository import PurchaseRepository
from schemas.purchases import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceRead,
    PurchaseInvoiceUpdate,
)


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

    async def update(self, bill_id: str, data: PurchaseInvoiceUpdate) -> PurchaseInvoiceRead:
        """Correct a posted supplier bill.

        Cancel-then-amend, exactly as for a sales invoice: the bill is reversed
        and a corrected copy posted under a new number ("<original>-1").
        """
        current = await self.get(bill_id)  # 404s if there is no such bill
        self._ensure_amendable(current)
        return await self.repo.amend(bill_id, data)

    @staticmethod
    def _ensure_amendable(bill: PurchaseInvoiceRead) -> None:
        """Refuse, before anything is cancelled, what ERPNext would refuse after.

        See SalesService._ensure_amendable — same reasoning, other side of the
        ledger.
        """
        if bill.is_opening:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{bill.id} is an opening balance from the first-time books "
                "setup, not a purchase. Editing it would leave the opening "
                "balances out of step with the ledger.",
            )
        paid = bill.grand_total - bill.outstanding_amount
        if paid > 0.005 and not bill.is_cancelled:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{bill.id} already has {paid:,.0f} XAF paid against it, so it "
                "cannot be cancelled. Cancel the payment first, or raise a "
                "debit note instead of editing the bill.",
            )
