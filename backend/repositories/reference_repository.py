"""Reference data for form pickers: the selectable values ERPNext will accept.

ERPNext organises master data as trees. The root of each tree ("All Customer
Groups", "All Territories") exists to hold the branches and **cannot be selected
on a transaction** — picking one fails with "Cannot select a Group type Customer
Group". A form that offers the whole tree therefore offers choices guaranteed to
fail, which is exactly how customer creation broke: the create form defaulted to
the root node.

So every list here filters `is_group = 0`. What comes back is only what can
actually be chosen.
"""

from __future__ import annotations

from integrations.erpnext import ERPNextClient


class ReferenceRepository:
    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def _leaves(self, doctype: str, limit: int = 200) -> list[str]:
        docs = await self.client.list_documents(
            doctype,
            fields=["name"],
            filters=[["is_group", "=", 0]],
            limit=limit,
            order_by="name asc",
        )
        return [d["name"] for d in docs if d.get("name")]

    async def customer_groups(self) -> list[str]:
        return await self._leaves("Customer Group")

    async def supplier_groups(self) -> list[str]:
        return await self._leaves("Supplier Group")

    async def territories(self) -> list[str]:
        return await self._leaves("Territory")

    async def item_groups(self) -> list[str]:
        return await self._leaves("Item Group")

    async def warehouses(self) -> list[str]:
        return await self._leaves("Warehouse")

    async def uoms(self, limit: int = 200) -> list[str]:
        # UOM is not a tree, so there is no is_group to filter on.
        docs = await self.client.list_documents(
            "UOM", fields=["name"], limit=limit, order_by="name asc"
        )
        return [d["name"] for d in docs if d.get("name")]
