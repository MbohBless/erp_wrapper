"""Batch data-access (repository pattern) backed by the ERPNext Batch DocType.

Carries batch numbers and expiry dates for stock items.
"""

from integrations.erpnext import ERPNextClient, ERPNextNotFound
from schemas.inventory import BatchCreate, BatchRead
from utils.mapping import to_erpnext

_FIELD_MAP = {
    "batch_id": "batch_id",
    "item_code": "item",
    "expiry_date": "expiry_date",
    "manufacturing_date": "manufacturing_date",
}
_READ_FIELDS = ["name", *_FIELD_MAP.values(), "batch_qty"]


def _to_erpnext(data: dict) -> dict:
    return to_erpnext(data, _FIELD_MAP)


def _from_erpnext(doc: dict) -> BatchRead:
    return BatchRead(
        id=doc.get("name"),
        batch_id=doc.get("batch_id") or doc.get("name"),
        item_code=doc.get("item") or "",
        expiry_date=doc.get("expiry_date") or None,
        manufacturing_date=doc.get("manufacturing_date") or None,
        qty=doc.get("batch_qty"),
    )


class BatchRepository:
    DOCTYPE = "Batch"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(self, limit: int = 50, start: int = 0) -> list[BatchRead]:
        docs = await self.client.list_documents(
            self.DOCTYPE, fields=_READ_FIELDS, limit=limit, start=start
        )
        return [_from_erpnext(doc) for doc in docs]

    async def get(self, name: str) -> BatchRead | None:
        try:
            doc = await self.client.get_document(self.DOCTYPE, name)
        except ERPNextNotFound:
            return None
        return _from_erpnext(doc)

    async def create(self, data: BatchCreate) -> BatchRead:
        payload = _to_erpnext(data.model_dump(exclude_none=True))
        doc = await self.client.create_document(self.DOCTYPE, payload)
        return _from_erpnext(doc)
