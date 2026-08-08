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

# ERPNext's Maintenance Visit Purpose row requires a Sales Person and a
# work_done note. Neither maps onto anything the caller must supply, so both
# have a fallback rather than making the API stricter than the domain needs.
_SALES_PERSON_ROOT = "Sales Team"
_DEFAULT_ENGINEER = "Unassigned"
_DEFAULT_WORK_DONE = "Maintenance visit"


def _erpnext_lifecycle(status: str | None) -> dict:
    """ERPNext's own mandatory lifecycle fields, derived from the ticket status.

    The DocType requires `completion_status` and `maintenance_type`, which
    overlap with — but are not the same as — this API's `status`. Rather than
    exposing ERPNext's vocabulary through the API, the ticket status is the
    single source of truth and these are derived from it.

    Both are mandatory, so omitting them fails the create outright.
    """
    return {
        "completion_status": (
            "Fully Completed" if status == "Completed" else "Partially Completed"
        ),
        "maintenance_type": "Scheduled" if status == "Scheduled" else "Unscheduled",
    }


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

    async def _service_person(self, engineer: str | None) -> str:
        """Resolve an engineer name to an ERPNext Sales Person, creating it once.

        ERPNext models the person who performed a visit as a Sales Person link,
        which does not match this domain — but it is what the DocType requires,
        and it is mandatory. A fresh install ships only the group node "Sales
        Team", and a group cannot be selected, so without this every maintenance
        ticket fails.

        The record is created under Sales Team on first use rather than being
        pre-seeded, so the engineer list follows whoever is actually named on
        tickets instead of a list someone has to maintain by hand.
        """
        name = (engineer or "").strip() or _DEFAULT_ENGINEER
        existing = await self.client.list_documents(
            "Sales Person", filters=[["name", "=", name]], fields=["name"], limit=1
        )
        if existing:
            return existing[0]["name"]
        created = await self.client.create_document(
            "Sales Person",
            {"sales_person_name": name, "parent_sales_person": _SALES_PERSON_ROOT,
             "is_group": 0},
        )
        return created.get("name", name)

    async def create(self, data: MaintenanceCreate) -> MaintenanceRead:
        payload = _to_erpnext(data.model_dump(exclude_none=True))
        payload.update(_erpnext_lifecycle(data.status))

        # ERPNext requires at least one row in the purpose table, with
        # service_person and work_done both set. The API models a ticket as a
        # single visit, so one row carries it.
        #
        # Without this the DocType rejects every create with "Add Items in the
        # Purpose Table" — and the test fake does not enforce mandatory child
        # tables, which is why the suite stayed green while the real endpoint
        # could not create a single ticket.
        payload["purposes"] = [
            {
                "service_person": await self._service_person(data.engineer),
                "work_done": data.description or _DEFAULT_WORK_DONE,
                "description": data.description or _DEFAULT_WORK_DONE,
                **({"serial_no": data.equipment} if data.equipment else {}),
            }
        ]
        doc = await self.client.create_document(self.DOCTYPE, payload)
        return _from_erpnext(doc)

    async def update(self, name: str, data: dict) -> MaintenanceRead:
        payload = _to_erpnext(data)
        if data.get("status"):
            payload.update(_erpnext_lifecycle(data["status"]))
        doc = await self.client.update_document(self.DOCTYPE, name, payload)
        return _from_erpnext(doc)

    async def delete(self, name: str) -> None:
        await self.client.delete_document(self.DOCTYPE, name)
