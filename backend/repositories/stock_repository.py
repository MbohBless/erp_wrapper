"""Product stock levels (read-only) backed by the ERPNext Bin DocType.

ERPNext maintains one Bin per (item, warehouse) with the computed quantities.
"""

from integrations.erpnext import ERPNextClient
from schemas.inventory import StockLevel

_READ_FIELDS = [
    "item_code",
    "warehouse",
    "actual_qty",
    "reserved_qty",
    "projected_qty",
]


def _from_erpnext(doc: dict) -> StockLevel:
    return StockLevel(
        item_code=doc.get("item_code"),
        warehouse=doc.get("warehouse"),
        actual_qty=doc.get("actual_qty") or 0,
        reserved_qty=doc.get("reserved_qty"),
        projected_qty=doc.get("projected_qty"),
    )


class StockRepository:
    DOCTYPE = "Bin"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(
        self,
        item_code: str | None = None,
        warehouse: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[StockLevel]:
        filters: list = []
        if item_code:
            filters.append(["item_code", "=", item_code])
        if warehouse:
            filters.append(["warehouse", "=", warehouse])
        docs = await self.client.list_documents(
            self.DOCTYPE,
            fields=_READ_FIELDS,
            filters=filters or None,
            limit=limit,
            start=start,
        )
        return [_from_erpnext(doc) for doc in docs]
