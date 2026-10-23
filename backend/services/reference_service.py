"""Reference data business logic.

Read-only. These are the values a form may offer, and nothing here creates
master data — a dropdown that can invent a customer group is a dropdown that
will.
"""

from repositories.reference_repository import ReferenceRepository
from schemas.reference import ReferenceOptions


class ReferenceService:
    def __init__(self, repo: ReferenceRepository) -> None:
        self.repo = repo

    async def options(self) -> ReferenceOptions:
        return ReferenceOptions(
            customer_groups=await self.repo.customer_groups(),
            supplier_groups=await self.repo.supplier_groups(),
            territories=await self.repo.territories(),
            item_groups=await self.repo.item_groups(),
            warehouses=await self.repo.warehouses(),
            uoms=await self.repo.uoms(),
        )

    async def default_item_group(self) -> str | None:
        """A selectable item category, for when a caller supplies none.

        Same reasoning as `default_customer_group`: the tree root looks
        selectable and never is, so a product created without a category would
        otherwise be refused over a field the user never chose.
        """
        groups = await self.repo.item_groups()
        if not groups:
            return None
        for preferred in ("Consumable", "Products"):
            if preferred in groups:
                return preferred
        return groups[0]

    async def default_warehouse(self) -> str | None:
        """The warehouse stock actually moves through.

        Same rule the goods-movement form preselects with, so a sale draws from
        the place a receipt put the goods. That agreement cannot be left to
        ERPNext: told nothing, it takes the warehouse from the *item's* default,
        which it copies from Stock Settings when the item is created — on a
        fresh site, "Stores". Receive into Finished Goods and sell with stock
        update on, and the invoice looks for the goods somewhere they have never
        been and fails with a negative-stock error naming a warehouse the user
        has never chosen.

        Prefers Finished Goods: this is a distribution business, devices arrive
        finished and leave finished. Falls back to the sole warehouse when there
        is only one, and to nothing when the choice is genuinely ambiguous —
        better ERPNext's default than a guess between two real candidates.
        """
        warehouses = await self.repo.warehouses()
        for warehouse in warehouses:
            if "finished goods" in warehouse.lower():
                return warehouse
        return warehouses[0] if len(warehouses) == 1 else None

    async def default_customer_group(self) -> str | None:
        """A selectable customer group, preferring the conventional one.

        Used when a caller supplies a group ERPNext will not accept — the root
        node — so the request succeeds with a sensible value rather than failing
        with an error about a field the user never chose.
        """
        groups = await self.repo.customer_groups()
        if not groups:
            return None
        for preferred in ("Commercial", "Individual"):
            if preferred in groups:
                return preferred
        return groups[0]
