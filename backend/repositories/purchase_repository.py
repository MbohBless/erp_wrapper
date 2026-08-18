"""Purchase invoice data-access backed by the ERPNext Purchase Invoice DocType.

Creation goes through the sanctioned integrations.erpnext.create_purchase wrapper
(which posts + submits the supplier bill to the ledger).

An *edit* of a posted bill is a cancel-then-amend, because ERPNext has no
in-place update for a submitted document — see `amend` below.
"""

from integrations.erpnext import ERPNextClient, ERPNextNotFound, create_purchase
from schemas.purchases import (
    BillLine,
    PurchaseInvoiceCreate,
    PurchaseInvoiceRead,
    PurchaseInvoiceUpdate,
)
from utils.mapping import to_float as _num

_LIST_FIELDS = [
    "name",
    "supplier",
    "posting_date",
    "due_date",
    "bill_no",
    "grand_total",
    "outstanding_amount",
    "status",
    "docstatus",
    "amended_from",
    "is_opening",
]

# docstatus 2 = cancelled: reversed, kept only as the trail behind an
# amendment. Listing it beside its replacement would show one purchase twice.
_NOT_CANCELLED = ["docstatus", "!=", 2]


def _from_erpnext(doc: dict) -> PurchaseInvoiceRead:
    grand = _num(doc.get("grand_total"))
    outstanding = _num(doc.get("outstanding_amount"))
    status = doc.get("status") or ("Paid" if grand > 0 and outstanding <= 0 else "Unpaid")
    items = [
        BillLine(
            item_code=it.get("item_code"),
            qty=_num(it.get("qty")),
            rate=_num(it.get("rate")),
            amount=_num(it.get("amount") or _num(it.get("qty")) * _num(it.get("rate"))),
        )
        for it in doc.get("items", [])
    ]
    return PurchaseInvoiceRead(
        id=doc.get("name"),
        supplier=doc.get("supplier"),
        posting_date=doc.get("posting_date"),
        due_date=doc.get("due_date"),
        bill_no=doc.get("bill_no") or None,
        grand_total=grand,
        outstanding_amount=outstanding,
        status=status,
        remarks=doc.get("remarks") or None,
        items=items,
        amended_from=doc.get("amended_from") or None,
        is_cancelled=int(_num(doc.get("docstatus"))) == 2,
        # A Select ("No"/"Yes"), not a check — see the note in sales_repository.
        is_opening=str(doc.get("is_opening") or "No") == "Yes",
    )


def _line_rows(items) -> list[dict]:
    """Item rows as ERPNext wants them. Shared by create and amend so a
    correction cannot drift from the shape the original was posted with."""
    return [
        {"item_code": line.item_code, "qty": line.qty, "rate": line.rate}
        for line in items
    ]


class PurchaseRepository:
    DOCTYPE = "Purchase Invoice"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(
        self,
        search: str | None = None,
        status: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[PurchaseInvoiceRead]:
        filters: list = [_NOT_CANCELLED]
        if search:
            filters.append(["supplier", "like", f"%{search}%"])
        if status:
            filters.append(["status", "=", status])
        docs = await self.client.list_documents(
            self.DOCTYPE,
            fields=_LIST_FIELDS,
            filters=filters,
            limit=limit,
            start=start,
            order_by="posting_date desc",
        )
        return [_from_erpnext(doc) for doc in docs]

    async def get(self, name: str) -> PurchaseInvoiceRead | None:
        try:
            doc = await self.client.get_document(self.DOCTYPE, name)
        except ERPNextNotFound:
            return None
        return _from_erpnext(doc)

    async def create(self, data: PurchaseInvoiceCreate) -> PurchaseInvoiceRead:
        return _from_erpnext(await self._post(data))

    async def amend(self, name: str, data: PurchaseInvoiceUpdate) -> PurchaseInvoiceRead:
        """Replace a posted bill: cancel it, then post the corrected copy.

        Same shape, same caveats and same resume behaviour as
        `SalesRepository.amend` — read the docstring there; the two must stay in
        step, because a correction that is safe on one side of the ledger and
        not the other is worse than neither.
        """
        doc = await self.client.get_document(self.DOCTYPE, name)
        docstatus = int(_num(doc.get("docstatus")))

        if docstatus == 2:
            existing = await self.client.list_documents(
                self.DOCTYPE,
                fields=["name"],
                filters=[["amended_from", "=", name], _NOT_CANCELLED],
                limit=1,
            )
            if existing:
                already = await self.get(existing[0]["name"])
                if already is not None:
                    return already
        elif docstatus == 1:
            await self.client.cancel_document(self.DOCTYPE, name)
        else:
            await self.client.update_document(self.DOCTYPE, name, self._payload(data))
            return _from_erpnext(await self.client.submit_document(self.DOCTYPE, name))

        return _from_erpnext(await self._post(data, amended_from=name))

    def _payload(self, data: PurchaseInvoiceCreate) -> dict:
        """The document body, for the in-place update of a draft."""
        payload: dict = {"supplier": data.supplier, "items": _line_rows(data.items)}
        payload["bill_no"] = data.bill_no or ""
        if data.posting_date:
            payload["posting_date"] = data.posting_date
            payload["set_posting_time"] = 1
        payload["remarks"] = data.remarks or ""
        return payload

    async def _post(
        self, data: PurchaseInvoiceCreate, amended_from: str | None = None
    ) -> dict:
        return await create_purchase(
            self.client,
            supplier=data.supplier,
            items=_line_rows(data.items),
            bill_no=data.bill_no,
            posting_date=data.posting_date,
            remarks=data.remarks,
            amended_from=amended_from,
            submit=True,
        )
