"""Supplier data-access (repository pattern) backed by the ERPNext DocType.

This is the single place that knows how the domain Supplier maps onto ERPNext
"Supplier" fields. The non-native attributes (contact, phone, email, address,
lead time) map to Custom Fields on the ERPNext Supplier DocType — see the
`custom_*` targets below; those Custom Fields must exist in ERPNext.
"""

from integrations.erpnext import ERPNextClient, ERPNextNotFound
from schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from utils.mapping import to_erpnext

# domain attribute -> ERPNext field
_FIELD_MAP: dict[str, str] = {
    "name": "supplier_name",
    "supplier_group": "supplier_group",
    "supplier_type": "supplier_type",
    "tax_id": "tax_id",
    "disabled": "disabled",
    "contact_person": "custom_contact_person",
    "phone": "custom_phone",
    "email": "custom_email",
    "address": "custom_address",
    "lead_time_days": "custom_lead_time_days",
}

# ERPNext fields we request back when reading (plus the document "name" id).
_READ_FIELDS = ["name", *_FIELD_MAP.values()]


def _to_erpnext(data: dict) -> dict:
    return to_erpnext(data, _FIELD_MAP, bool_fields=("disabled",))


def _from_erpnext(doc: dict) -> SupplierRead:
    """Translate an ERPNext document back into a SupplierRead."""
    return SupplierRead(
        id=doc.get("name"),
        name=doc.get("supplier_name") or doc.get("name"),
        supplier_group=doc.get("supplier_group") or "All Supplier Groups",
        supplier_type=doc.get("supplier_type") or "Company",
        tax_id=doc.get("tax_id") or None,
        contact_person=doc.get("custom_contact_person") or None,
        phone=doc.get("custom_phone") or None,
        email=doc.get("custom_email") or None,
        address=doc.get("custom_address") or None,
        lead_time_days=doc.get("custom_lead_time_days"),
        disabled=bool(doc.get("disabled")),
    )


class SupplierRepository:
    DOCTYPE = "Supplier"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(
        self,
        search: str | None = None,
        supplier_type: str | None = None,
        group: str | None = None,
        disabled: bool | None = None,
        limit: int = 20,
        start: int = 0,
    ) -> list[SupplierRead]:
        filters: list = []
        if search:
            filters.append(["supplier_name", "like", f"%{search}%"])
        if supplier_type:
            filters.append(["supplier_type", "=", supplier_type])
        if group:
            filters.append(["supplier_group", "=", group])
        # Applied by ERPNext, not after the fact. Filtering the fetched page
        # here would only ever filter the page in front of the user and
        # silently hide every match on the others.
        if disabled is not None:
            filters.append(["disabled", "=", 1 if disabled else 0])
        docs = await self.client.list_documents(
            self.DOCTYPE,
            fields=_READ_FIELDS,
            filters=filters or None,
            limit=limit,
            start=start,
            order_by="supplier_name asc",
        )
        return [_from_erpnext(doc) for doc in docs]

    async def get(self, name: str) -> SupplierRead | None:
        try:
            doc = await self.client.get_document(self.DOCTYPE, name)
        except ERPNextNotFound:
            return None
        return _from_erpnext(doc)

    async def create(self, data: SupplierCreate) -> SupplierRead:
        payload = _to_erpnext(data.model_dump(exclude_none=True))
        doc = await self.client.create_document(self.DOCTYPE, payload)
        return _from_erpnext(doc)

    async def update(self, name: str, data: SupplierUpdate) -> SupplierRead:
        payload = _to_erpnext(data.model_dump(exclude_unset=True, exclude_none=True))
        doc = await self.client.update_document(self.DOCTYPE, name, payload)
        return _from_erpnext(doc)

    async def delete(self, name: str) -> None:
        await self.client.delete_document(self.DOCTYPE, name)
