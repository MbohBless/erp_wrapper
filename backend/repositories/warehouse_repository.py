"""Warehouse data-access (repository pattern) backed by the ERPNext Warehouse DocType."""

from integrations.erpnext import ERPNextClient, ERPNextNotFound
from schemas.inventory import WarehouseCreate, WarehouseRead, WarehouseUpdate
from utils.mapping import to_erpnext

_FIELD_MAP = {
    "name": "warehouse_name",
    "parent_warehouse": "parent_warehouse",
    "is_group": "is_group",
    "disabled": "disabled",
}
_READ_FIELDS = ["name", *_FIELD_MAP.values()]


def _to_erpnext(data: dict) -> dict:
    return to_erpnext(data, _FIELD_MAP, bool_fields=("is_group", "disabled"))


def _from_erpnext(doc: dict) -> WarehouseRead:
    return WarehouseRead(
        id=doc.get("name"),
        name=doc.get("warehouse_name") or doc.get("name"),
        parent_warehouse=doc.get("parent_warehouse") or None,
        is_group=bool(doc.get("is_group")),
        disabled=bool(doc.get("disabled")),
    )


class WarehouseRepository:
    DOCTYPE = "Warehouse"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(
        self, limit: int = 50, start: int = 0, include_disabled: bool = False
    ) -> list[WarehouseRead]:
        # A disabled warehouse is one someone deliberately retired. Offering it
        # invites stock into a location the next person will not think to look
        # in, and ERPNext refuses it on a transaction anyway.
        filters = None if include_disabled else [["disabled", "=", 0]]
        docs = await self.client.list_documents(
            self.DOCTYPE, fields=_READ_FIELDS, filters=filters,
            limit=limit, start=start
        )
        return [_from_erpnext(doc) for doc in docs]

    async def get(self, name: str) -> WarehouseRead | None:
        try:
            doc = await self.client.get_document(self.DOCTYPE, name)
        except ERPNextNotFound:
            return None
        return _from_erpnext(doc)

    async def create(self, data: WarehouseCreate) -> WarehouseRead:
        payload = _to_erpnext(data.model_dump(exclude_none=True))
        doc = await self.client.create_document(self.DOCTYPE, payload)
        return _from_erpnext(doc)

    async def update(self, name: str, data: WarehouseUpdate) -> WarehouseRead:
        payload = _to_erpnext(data.model_dump(exclude_unset=True, exclude_none=True))
        doc = await self.client.update_document(self.DOCTYPE, name, payload)
        return _from_erpnext(doc)

    async def delete(self, name: str) -> None:
        await self.client.delete_document(self.DOCTYPE, name)
