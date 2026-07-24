"""Product data-access (repository pattern) backed by the ERPNext "Item" DocType.

Single place mapping the domain Product onto ERPNext Item fields. Non-native
attributes (barcode, manufacturer, purchase/selling price) map to Custom Fields
(`custom_*`) that must exist on the ERPNext Item DocType. Proper pricing in
ERPNext uses Item Price / price lists; the price custom fields here are a
V1 convenience.
"""

from integrations.erpnext import ERPNextClient, ERPNextNotFound
from schemas.product import ProductCreate, ProductRead, ProductUpdate
from utils.mapping import to_erpnext

# domain attribute -> ERPNext field
_FIELD_MAP: dict[str, str] = {
    "name": "item_name",
    "sku": "item_code",
    "category": "item_group",
    "unit": "stock_uom",
    "image": "image",
    "disabled": "disabled",
    "barcode": "custom_barcode",
    "manufacturer": "custom_manufacturer",
    "purchase_price": "custom_purchase_price",
    "selling_price": "custom_selling_price",
}

_READ_FIELDS = ["name", *_FIELD_MAP.values()]


def _to_erpnext(data: dict) -> dict:
    return to_erpnext(data, _FIELD_MAP, bool_fields=("disabled",))


def _from_erpnext(doc: dict) -> ProductRead:
    return ProductRead(
        id=doc.get("name"),
        name=doc.get("item_name") or doc.get("name"),
        sku=doc.get("item_code") or doc.get("name"),
        category=doc.get("item_group") or "All Item Groups",
        unit=doc.get("stock_uom") or "Nos",
        image=doc.get("image") or None,
        barcode=doc.get("custom_barcode") or None,
        manufacturer=doc.get("custom_manufacturer") or None,
        purchase_price=doc.get("custom_purchase_price"),
        selling_price=doc.get("custom_selling_price"),
        disabled=bool(doc.get("disabled")),
    )


class ProductRepository:
    DOCTYPE = "Item"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(
        self,
        search: str | None = None,
        category: str | None = None,
        limit: int = 20,
        start: int = 0,
    ) -> list[ProductRead]:
        filters: list = []
        if search:
            filters.append(["item_name", "like", f"%{search}%"])
        if category:
            filters.append(["item_group", "=", category])
        docs = await self.client.list_documents(
            self.DOCTYPE,
            fields=_READ_FIELDS,
            filters=filters or None,
            limit=limit,
            start=start,
            order_by="item_name asc",
        )
        return [_from_erpnext(doc) for doc in docs]

    async def get(self, name: str) -> ProductRead | None:
        try:
            doc = await self.client.get_document(self.DOCTYPE, name)
        except ERPNextNotFound:
            return None
        return _from_erpnext(doc)

    async def create(self, data: ProductCreate) -> ProductRead:
        payload = _to_erpnext(data.model_dump(exclude_none=True))
        doc = await self.client.create_document(self.DOCTYPE, payload)
        return _from_erpnext(doc)

    async def update(self, name: str, data: ProductUpdate) -> ProductRead:
        payload = _to_erpnext(data.model_dump(exclude_unset=True, exclude_none=True))
        doc = await self.client.update_document(self.DOCTYPE, name, payload)
        return _from_erpnext(doc)

    async def delete(self, name: str) -> None:
        await self.client.delete_document(self.DOCTYPE, name)
