"""Goods movements backed by the ERPNext Stock Entry DocType.

Goods Received -> Material Receipt (items land in a target warehouse).
Goods Issued  -> Material Issue  (items leave a source warehouse).
Each Stock Entry is created and then submitted so it affects stock.
"""

from integrations.erpnext import ERPNextClient
from schemas.inventory import (
    GoodsIssueRequest,
    GoodsReceiptRequest,
    MovementLine,
    StockEntryLine,
    StockEntryRead,
)


def _line_payload(line: MovementLine, warehouse: str, incoming: bool) -> dict:
    item: dict = {"item_code": line.item_code, "qty": line.qty}
    if incoming:
        item["t_warehouse"] = warehouse
    else:
        item["s_warehouse"] = warehouse
    if line.batch_no:
        item["batch_no"] = line.batch_no
    if line.rate is not None:
        item["basic_rate"] = line.rate
    return item


def _from_erpnext(doc: dict) -> StockEntryRead:
    lines = [
        StockEntryLine(
            item_code=it.get("item_code"),
            qty=it.get("qty"),
            warehouse=it.get("t_warehouse") or it.get("s_warehouse"),
            batch_no=it.get("batch_no"),
        )
        for it in doc.get("items", [])
    ]
    return StockEntryRead(
        id=doc.get("name"),
        stock_entry_type=doc.get("stock_entry_type"),
        items=lines,
    )


class StockEntryRepository:
    DOCTYPE = "Stock Entry"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def _create_and_submit(self, payload: dict) -> StockEntryRead:
        doc = await self.client.create_document(self.DOCTYPE, payload)
        submitted = await self.client.submit_document(self.DOCTYPE, doc.get("name"))
        return _from_erpnext(submitted or doc)

    async def create_receipt(self, req: GoodsReceiptRequest) -> StockEntryRead:
        payload = {
            "stock_entry_type": "Material Receipt",
            "to_warehouse": req.warehouse,
            "items": [_line_payload(line, req.warehouse, True) for line in req.items],
        }
        return await self._create_and_submit(payload)

    async def create_issue(self, req: GoodsIssueRequest) -> StockEntryRead:
        payload = {
            "stock_entry_type": "Material Issue",
            "from_warehouse": req.warehouse,
            "items": [_line_payload(line, req.warehouse, False) for line in req.items],
        }
        return await self._create_and_submit(payload)
