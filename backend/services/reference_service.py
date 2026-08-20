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
