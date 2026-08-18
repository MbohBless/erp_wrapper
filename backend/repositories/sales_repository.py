"""Sales invoice data-access backed by the ERPNext Sales Invoice DocType.

Creation goes through the sanctioned integrations.erpnext.create_invoice wrapper
(which posts + submits the invoice to the ledger).

An *edit* of a posted invoice is a cancel-then-amend, because ERPNext has no
in-place update for a submitted document — see `amend` below.
"""

from integrations.erpnext import ERPNextClient, ERPNextNotFound, create_invoice
from schemas.sales import (
    InvoiceLine,
    SalesInvoiceCreate,
    SalesInvoiceRead,
    SalesInvoiceUpdate,
)
from utils.mapping import to_float as _num

_LIST_FIELDS = [
    "name",
    "customer",
    "posting_date",
    "due_date",
    "grand_total",
    "outstanding_amount",
    "status",
    "docstatus",
    "amended_from",
    "is_opening",
    "update_stock",
    "taxes_and_charges",
]

# docstatus 2 = cancelled. A cancelled invoice has had its ledger entries
# reversed and is only there as the trail behind an amendment, so listing it
# beside its replacement would show the same sale twice — once for real and
# once for nothing. The replacement carries `amended_from`, which is where the
# original stays visible.
_NOT_CANCELLED = ["docstatus", "!=", 2]


def _from_erpnext(doc: dict) -> SalesInvoiceRead:
    grand = _num(doc.get("grand_total"))
    outstanding = _num(doc.get("outstanding_amount"))
    status = doc.get("status") or ("Paid" if grand > 0 and outstanding <= 0 else "Unpaid")
    items = [
        InvoiceLine(
            item_code=it.get("item_code"),
            item_name=it.get("item_name") or None,
            qty=_num(it.get("qty")),
            rate=_num(it.get("rate")),
            amount=_num(it.get("amount") or _num(it.get("qty")) * _num(it.get("rate"))),
        )
        for it in doc.get("items", [])
    ]
    return SalesInvoiceRead(
        id=doc.get("name"),
        customer=doc.get("customer"),
        posting_date=doc.get("posting_date"),
        due_date=doc.get("due_date"),
        grand_total=grand,
        outstanding_amount=outstanding,
        status=status,
        remarks=doc.get("remarks") or None,
        items=items,
        update_stock=bool(_num(doc.get("update_stock"))),
        taxes_and_charges=doc.get("taxes_and_charges") or None,
        amended_from=doc.get("amended_from") or None,
        is_cancelled=int(_num(doc.get("docstatus"))) == 2,
        # `is_opening` is a Select on Sales Invoice ("No"/"Yes"), not a check —
        # truth-testing it directly would make every invoice look like an
        # opening entry, because "No" is a non-empty string.
        is_opening=str(doc.get("is_opening") or "No") == "Yes",
    )


def _line_rows(items) -> list[dict]:
    """Item rows as ERPNext wants them. Shared by create and amend so a
    correction cannot drift from the shape the original was posted with."""
    rows = []
    for line in items:
        row: dict = {"item_code": line.item_code, "qty": line.qty, "rate": line.rate}
        if getattr(line, "description", None):
            row["description"] = line.description
        rows.append(row)
    return rows


class SalesRepository:
    DOCTYPE = "Sales Invoice"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(
        self,
        search: str | None = None,
        status: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[SalesInvoiceRead]:
        filters: list = [_NOT_CANCELLED]
        if search:
            filters.append(["customer", "like", f"%{search}%"])
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

    async def get(self, name: str) -> SalesInvoiceRead | None:
        try:
            doc = await self.client.get_document(self.DOCTYPE, name)
        except ERPNextNotFound:
            return None
        return _from_erpnext(doc)

    async def create(self, data: SalesInvoiceCreate) -> SalesInvoiceRead:
        doc = await self._post(data)
        return _from_erpnext(doc)

    async def amend(self, name: str, data: SalesInvoiceUpdate) -> SalesInvoiceRead:
        """Replace a posted invoice: cancel it, then post the corrected copy.

        ERPNext cannot edit a submitted document, so this is the only way to
        change one. The replacement is named "<original>-1" and keeps
        `amended_from` pointing back at the original, which stays in ERPNext
        reversed rather than being rewritten — that pair *is* the audit trail.

        The two steps are not one transaction and cannot be. If the cancel
        succeeds and the re-post fails (a validation ERPNext only applies on
        submit, a stock shortfall, a dropped connection), the invoice is left
        cancelled with nothing standing in for it. That state is recoverable:
        calling this again resumes from the cancelled original instead of
        starting over. Which is exactly why it must not blindly re-post — see
        the lookup below.
        """
        doc = await self.client.get_document(self.DOCTYPE, name)
        docstatus = int(_num(doc.get("docstatus")))

        if docstatus == 2:
            # Resuming an interrupted amend. If the replacement did get posted
            # and only the response was lost, posting another would double the
            # revenue and leave two live invoices for one sale.
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
            # A draft — never one of ours, but one left in the ERPNext desk is
            # still editable in place, and cancelling it is not possible.
            await self.client.update_document(self.DOCTYPE, name, self._payload(data))
            return _from_erpnext(await self.client.submit_document(self.DOCTYPE, name))

        return _from_erpnext(await self._post(data, amended_from=name))

    def _payload(self, data: SalesInvoiceCreate) -> dict:
        """The document body, for the in-place update of a draft."""
        payload: dict = {"customer": data.customer, "items": _line_rows(data.items)}
        if data.due_date:
            payload["due_date"] = data.due_date
        if data.posting_date:
            payload["posting_date"] = data.posting_date
            payload["set_posting_time"] = 1
        payload["remarks"] = data.remarks or ""
        payload["update_stock"] = 1 if data.update_stock else 0
        if data.taxes_and_charges:
            payload["taxes_and_charges"] = data.taxes_and_charges
        return payload

    async def _post(
        self, data: SalesInvoiceCreate, amended_from: str | None = None
    ) -> dict:
        return await create_invoice(
            self.client,
            customer=data.customer,
            items=_line_rows(data.items),
            due_date=data.due_date,
            posting_date=data.posting_date,
            remarks=data.remarks,
            update_stock=data.update_stock,
            taxes_and_charges=data.taxes_and_charges,
            amended_from=amended_from,
            submit=True,
        )
