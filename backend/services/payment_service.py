"""Payment business logic (proxying the ERPNext Payment Entry DocType)."""

from repositories.payment_repository import PaymentRepository
from schemas.payments import PaymentPay, PaymentRead, PaymentReceive


class PaymentService:
    def __init__(self, repo: PaymentRepository) -> None:
        self.repo = repo

    async def list(self, limit: int = 50, start: int = 0) -> list[PaymentRead]:
        return await self.repo.list(limit, start)

    async def receive(self, data: PaymentReceive) -> PaymentRead:
        return await self.repo.record(
            "Sales Invoice", data.invoice_id, data.amount,
            data.mode_of_payment, data.posting_date, data.reference_no,
        )

    async def pay(self, data: PaymentPay) -> PaymentRead:
        return await self.repo.record(
            "Purchase Invoice", data.bill_id, data.amount,
            data.mode_of_payment, data.posting_date, data.reference_no,
        )
