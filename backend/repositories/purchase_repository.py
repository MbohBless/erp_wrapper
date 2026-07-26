"""Purchase invoice data-access backed by the ERPNext Purchase Invoice DocType.

Creation goes through the sanctioned integrations.erpnext.create_purchase wrapper
(which posts + submits the supplier bill to the ledger).
"""

from integrations.erpnext import ERPNextClient, ERPNextNotFound, create_purchase
from schemas.purchases import BillLine, PurchaseInvoiceCreate, PurchaseInvoiceRead
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
]


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
    )


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
        filters: list = []
        if search:
            filters.append(["supplier", "like", f"%{search}%"])
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

    async def get(self, name: str) -> PurchaseInvoiceRead | None:
        try:
            doc = await self.client.get_document(self.DOCTYPE, name)
        except ERPNextNotFound:
            return None
        return _from_erpnext(doc)

    async def create(self, data: PurchaseInvoiceCreate) -> PurchaseInvoiceRead:
        items = [
            {"item_code": line.item_code, "qty": line.qty, "rate": line.rate}
            for line in data.items
        ]
        doc = await create_purchase(
            self.client,
            supplier=data.supplier,
            items=items,
            bill_no=data.bill_no,
            posting_date=data.posting_date,
            remarks=data.remarks,
            submit=True,
        )
        return _from_erpnext(doc)
