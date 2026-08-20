"""Customer management business logic (proxying the ERPNext Customer DocType)."""

from fastapi import HTTPException, status

from repositories.customer_repository import CustomerRepository
from schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from services.reference_service import ReferenceService

# ERPNext tree roots. Selectable-looking, never selectable.
_GROUP_ROOTS = {"All Customer Groups", "All Territories"}


class CustomerService:
    def __init__(
        self, repo: CustomerRepository, reference: ReferenceService | None = None
    ) -> None:
        self.repo = repo
        self.reference = reference

    async def list(
        self,
        search: str | None = None,
        customer_type: str | None = None,
        group: str | None = None,
        disabled: bool | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[CustomerRead]:
        return await self.repo.list(search, customer_type, group, disabled, limit, start)

    async def get(self, name: str) -> CustomerRead:
        customer = await self.repo.get(name)
        if customer is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
        return customer

    async def _usable_group(self, given: str | None) -> str | None:
        """Turn an unusable customer group into one ERPNext will accept.

        The tree root cannot be selected, and neither can an empty value. Both
        arrive from clients that never made a real choice — the create form
        defaulted to the root — so substituting a selectable group is strictly
        better than a 502 about a field the user never touched.

        An explicitly chosen leaf is always left alone.
        """
        if given and given not in _GROUP_ROOTS:
            return given
        if self.reference is None:
            return None if given in _GROUP_ROOTS else given
        # None, not the root, when nothing selectable exists. Sending a value
        # ERPNext refuses guarantees a 417; omitting the field lets ERPNext
        # apply its own default and the record saves.
        return await self.reference.default_customer_group() or None

    async def create(self, data: CustomerCreate) -> CustomerRead:
        if await self.repo.get(data.name) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Customer already exists")
        data = data.model_copy(
            update={"customer_group": await self._usable_group(data.customer_group)}
        )
        return await self.repo.create(data)

    async def update(self, name: str, data: CustomerUpdate) -> CustomerRead:
        await self.get(name)  # 404 if missing
        if data.customer_group is not None:
            data = data.model_copy(
                update={"customer_group": await self._usable_group(data.customer_group)}
            )
        return await self.repo.update(name, data)

    async def delete(self, name: str) -> None:
        await self.get(name)  # 404 if missing
        await self.repo.delete(name)
