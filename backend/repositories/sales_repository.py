"""Sales invoice data-access backed by the ERPNext Sales Invoice DocType.

Creation goes through the sanctioned integrations.erpnext.create_invoice wrapper
(which posts + submits the invoice to the ledger).
"""

from integrations.erpnext import ERPNextClient, ERPNextNotFound, create_invoice
from schemas.sales import InvoiceLine, SalesInvoiceCreate, SalesInvoiceRead
from utils.mapping import to_float as _num

_LIST_FIELDS = [
    "name",
    "customer",
    "posting_date",
    "due_date",
    "grand_total",
    "outstanding_amount",
    "status",
]


def _from_erpnext(doc: dict) -> SalesInvoiceRead:
    grand = _num(doc.get("grand_total"))
    outstanding = _num(doc.get("outstanding_amount"))
    status = doc.get("status") or ("Paid" if grand > 0 and outstanding <= 0 else "Unpaid")
    items = [
        InvoiceLine(
            item_code=it.get("item_code"),
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
    )


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
        filters: list = []
        if search:
            filters.append(["customer", "like", f"%{search}%"])
        if status:
            filters.append(["status", "=", status])
        docs = await self.client.list_documents(
            self.DOCTYPE,
            fields=_LIST_FIELDS,
            filters=filters or None,
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
        items = []
        for line in data.items:
            row: dict = {"item_code": line.item_code, "qty": line.qty, "rate": line.rate}
            if line.description:
                row["description"] = line.description
            items.append(row)
        doc = await create_invoice(
            self.client,
            customer=data.customer,
            items=items,
            due_date=data.due_date,
            posting_date=data.posting_date,
            remarks=data.remarks,
            update_stock=data.update_stock,
            taxes_and_charges=data.taxes_and_charges,
            submit=True,
        )
        return _from_erpnext(doc)
