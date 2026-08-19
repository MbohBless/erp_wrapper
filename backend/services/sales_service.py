"""Sales invoice business logic (proxying the ERPNext Sales Invoice DocType)."""

from fastapi import HTTPException, status

from repositories.product_repository import ProductRepository
from repositories.sales_repository import SalesRepository
from schemas.sales import SalesInvoiceCreate, SalesInvoiceRead, SalesInvoiceUpdate


class SalesService:
    def __init__(self, repo: SalesRepository, products: ProductRepository) -> None:
        self.repo = repo
        # Needed to stamp each line with the product's own selling price. Read
        # here rather than taken from the request: a list price the caller
        # supplies is a list price the caller can invent, and the whole value of
        # recording it is that the discount it implies is not self-declared.
        self.products = products

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
        self._check_commission(data)
        return await self.repo.create(data, await self._list_rates(data.items))

    @staticmethod
    def _check_commission(data: SalesInvoiceCreate) -> None:
        """A commissioned sale has to say whose commission it was.

        The flag on its own answers "was this discounted deliberately?" but not
        "by whom, and is it worth continuing?", which is the question anyone
        looks at these for.
        """
        if data.is_commissioned and not (data.commission_agent or "").strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "A commissioned sale needs the name of the agent it was "
                "brokered by.",
            )
        if not data.is_commissioned and (data.commission_agent or "").strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "There is a commission agent on this invoice but it is not "
                "marked as a commissioned sale.",
            )

    async def _list_rates(self, items) -> dict[str, float]:
        """Each item's own selling price, for ERPNext's `price_list_rate`.

        One lookup per *distinct* item, not per line — an invoice repeating the
        same product should not pay for it twice. An item with no price on file
        is simply absent, and its line then records no list price rather than a
        false zero.
        """
        rates: dict[str, float] = {}
        for code in {line.item_code for line in items}:
            product = await self.products.get(code)
            if product is not None and product.selling_price:
                rates[code] = float(product.selling_price)
        return rates

    async def update(self, invoice_id: str, data: SalesInvoiceUpdate) -> SalesInvoiceRead:
        """Correct a posted invoice.

        There is no in-place edit: the invoice is cancelled and a corrected copy
        posted in its place, under a new number ("<original>-1"). The caller
        needs to know that, which is why the route is documented as an amend
        rather than an update.
        """
        current = await self.get(invoice_id)  # 404s if there is no such invoice
        self._check_commission(data)
        self._ensure_amendable(current)
        return await self.repo.amend(invoice_id, data, await self._list_rates(data.items))

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
