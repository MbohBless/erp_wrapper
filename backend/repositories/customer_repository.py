"""Customer data-access (repository pattern) backed by the ERPNext Customer DocType.

Non-native attributes (contact, phone, email, address) map to Custom Fields
(`custom_*`) that must exist on the ERPNext Customer DocType.
"""

from integrations.erpnext import ERPNextClient, ERPNextNotFound
from schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from utils.mapping import to_erpnext

_FIELD_MAP: dict[str, str] = {
    "name": "customer_name",
    "customer_group": "customer_group",
    "customer_type": "customer_type",
    "territory": "territory",
    "tax_id": "tax_id",
    "disabled": "disabled",
    "contact_person": "custom_contact_person",
    "phone": "custom_phone",
    "email": "custom_email",
    "address": "custom_address",
}
_READ_FIELDS = ["name", *_FIELD_MAP.values(), "outstanding_amount"]


def _to_erpnext(data: dict) -> dict:
    return to_erpnext(data, _FIELD_MAP, bool_fields=("disabled",))


def _from_erpnext(doc: dict) -> CustomerRead:
    balance = doc.get("outstanding_amount")
    return CustomerRead(
        id=doc.get("name"),
        name=doc.get("customer_name") or doc.get("name"),
        customer_group=doc.get("customer_group") or "All Customer Groups",
        customer_type=doc.get("customer_type") or "Company",
        territory=doc.get("territory") or "All Territories",
        tax_id=doc.get("tax_id") or None,
        contact_person=doc.get("custom_contact_person") or None,
        phone=doc.get("custom_phone") or None,
        email=doc.get("custom_email") or None,
        address=doc.get("custom_address") or None,
        disabled=bool(doc.get("disabled")),
        outstanding_balance=float(balance) if balance is not None else None,
    )


class CustomerRepository:
    DOCTYPE = "Customer"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(
        self,
        search: str | None = None,
        customer_type: str | None = None,
        group: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[CustomerRead]:
        filters: list = []
        if search:
            filters.append(["customer_name", "like", f"%{search}%"])
        if customer_type:
            filters.append(["customer_type", "=", customer_type])
        if group:
            filters.append(["customer_group", "=", group])
        docs = await self.client.list_documents(
            self.DOCTYPE,
            fields=_READ_FIELDS,
            filters=filters or None,
            limit=limit,
            start=start,
            order_by="customer_name asc",
        )
        return [_from_erpnext(doc) for doc in docs]

    async def get(self, name: str) -> CustomerRead | None:
        try:
            doc = await self.client.get_document(self.DOCTYPE, name)
        except ERPNextNotFound:
            return None
        return _from_erpnext(doc)

    async def create(self, data: CustomerCreate) -> CustomerRead:
        payload = _to_erpnext(data.model_dump(exclude_none=True))
        doc = await self.client.create_document(self.DOCTYPE, payload)
        return _from_erpnext(doc)

    async def update(self, name: str, data: CustomerUpdate) -> CustomerRead:
        payload = _to_erpnext(data.model_dump(exclude_unset=True, exclude_none=True))
        doc = await self.client.update_document(self.DOCTYPE, name, payload)
        return _from_erpnext(doc)

    async def delete(self, name: str) -> None:
        await self.client.delete_document(self.DOCTYPE, name)
