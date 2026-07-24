"""Maintenance data-access backed by the ERPNext Maintenance Visit DocType.

Ticket details (engineer, parts used, signature, operational status) map to
Custom Fields (`custom_*`) that must exist on the ERPNext Maintenance Visit DocType.
"""

from integrations.erpnext import ERPNextClient, ERPNextNotFound
from schemas.maintenance import MaintenanceCreate, MaintenanceRead
from utils.mapping import to_erpnext

_FIELD_MAP = {
    "customer": "customer",
    "visit_date": "mntc_date",
    "equipment": "custom_serial_no",
    "engineer": "custom_engineer",
    "description": "custom_description",
    "parts_used": "custom_parts_used",
    "status": "custom_status",
    "customer_signed": "custom_customer_signed",
}
_READ_FIELDS = ["name", *_FIELD_MAP.values()]


def _to_erpnext(data: dict) -> dict:
    return to_erpnext(data, _FIELD_MAP, bool_fields=("customer_signed",))


def _from_erpnext(doc: dict) -> MaintenanceRead:
    return MaintenanceRead(
        id=doc.get("name"),
        customer=doc.get("customer") or "",
        equipment=doc.get("custom_serial_no") or None,
        engineer=doc.get("custom_engineer") or None,
        visit_date=doc.get("mntc_date") or None,
        description=doc.get("custom_description") or None,
        parts_used=doc.get("custom_parts_used") or None,
        status=doc.get("custom_status") or "Open",
        customer_signed=bool(doc.get("custom_customer_signed")),
    )


class MaintenanceRepository:
    DOCTYPE = "Maintenance Visit"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(
        self,
        search: str | None = None,
        status: str | None = None,
        engineer: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[MaintenanceRead]:
        filters: list = []
        if search:
            filters.append(["customer", "like", f"%{search}%"])
        if status:
            filters.append(["custom_status", "=", status])
        if engineer:
            filters.append(["custom_engineer", "=", engineer])
        docs = await self.client.list_documents(
            self.DOCTYPE,
            fields=_READ_FIELDS,
            filters=filters or None,
            limit=limit,
            start=start,
            order_by="mntc_date desc",
        )
        return [_from_erpnext(doc) for doc in docs]

    async def get(self, name: str) -> MaintenanceRead | None:
        try:
            doc = await self.client.get_document(self.DOCTYPE, name)
        except ERPNextNotFound:
            return None
        return _from_erpnext(doc)

    async def create(self, data: MaintenanceCreate) -> MaintenanceRead:
        payload = _to_erpnext(data.model_dump(exclude_none=True))
        doc = await self.client.create_document(self.DOCTYPE, payload)
        return _from_erpnext(doc)

    async def update(self, name: str, data: dict) -> MaintenanceRead:
        doc = await self.client.update_document(self.DOCTYPE, name, _to_erpnext(data))
        return _from_erpnext(doc)

    async def delete(self, name: str) -> None:
        await self.client.delete_document(self.DOCTYPE, name)
