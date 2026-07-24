"""Equipment data-access backed by the ERPNext Serial No DocType.

Non-native attributes (installation date, operational status) map to Custom
Fields (`custom_*`) that must exist on the ERPNext Serial No DocType.
"""

from integrations.erpnext import ERPNextClient, ERPNextNotFound
from schemas.equipment import EquipmentCreate, EquipmentRead, EquipmentUpdate
from utils.mapping import to_erpnext

_FIELD_MAP = {
    "serial_no": "serial_no",
    "item_code": "item_code",
    "customer": "customer",
    "warranty_expiry_date": "warranty_expiry_date",
    "installation_date": "custom_installation_date",
    "status": "custom_status",
}
_READ_FIELDS = ["name", *_FIELD_MAP.values(), "item_name"]


def _to_erpnext(data: dict) -> dict:
    return to_erpnext(data, _FIELD_MAP)


def _from_erpnext(doc: dict) -> EquipmentRead:
    return EquipmentRead(
        id=doc.get("name"),
        serial_no=doc.get("serial_no") or doc.get("name"),
        item_code=doc.get("item_code") or "",
        item_name=doc.get("item_name") or None,
        customer=doc.get("customer") or None,
        installation_date=doc.get("custom_installation_date") or None,
        warranty_expiry_date=doc.get("warranty_expiry_date") or None,
        status=doc.get("custom_status") or "In Store",
    )


class EquipmentRepository:
    DOCTYPE = "Serial No"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(
        self,
        search: str | None = None,
        status: str | None = None,
        customer: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[EquipmentRead]:
        filters: list = []
        if search:
            filters.append(["serial_no", "like", f"%{search}%"])
        if status:
            filters.append(["custom_status", "=", status])
        if customer:
            filters.append(["customer", "=", customer])
        docs = await self.client.list_documents(
            self.DOCTYPE,
            fields=_READ_FIELDS,
            filters=filters or None,
            limit=limit,
            start=start,
            order_by="serial_no asc",
        )
        return [_from_erpnext(doc) for doc in docs]

    async def get(self, name: str) -> EquipmentRead | None:
        try:
            doc = await self.client.get_document(self.DOCTYPE, name)
        except ERPNextNotFound:
            return None
        return _from_erpnext(doc)

    async def create(self, data: EquipmentCreate) -> EquipmentRead:
        payload = _to_erpnext(data.model_dump(exclude_none=True))
        doc = await self.client.create_document(self.DOCTYPE, payload)
        return _from_erpnext(doc)

    async def update(self, name: str, data: dict) -> EquipmentRead:
        doc = await self.client.update_document(self.DOCTYPE, name, _to_erpnext(data))
        return _from_erpnext(doc)

    async def delete(self, name: str) -> None:
        await self.client.delete_document(self.DOCTYPE, name)
