"""Customer management business logic (proxying the ERPNext Customer DocType)."""

from fastapi import HTTPException, status

from repositories.customer_repository import CustomerRepository
from schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate


class CustomerService:
    def __init__(self, repo: CustomerRepository) -> None:
        self.repo = repo

    async def list(
        self,
        search: str | None = None,
        customer_type: str | None = None,
        group: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[CustomerRead]:
        return await self.repo.list(search, customer_type, group, limit, start)

    async def get(self, name: str) -> CustomerRead:
        customer = await self.repo.get(name)
        if customer is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
        return customer

    async def create(self, data: CustomerCreate) -> CustomerRead:
        if await self.repo.get(data.name) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Customer already exists")
        return await self.repo.create(data)

    async def update(self, name: str, data: CustomerUpdate) -> CustomerRead:
        await self.get(name)  # 404 if missing
        return await self.repo.update(name, data)

    async def delete(self, name: str) -> None:
        await self.get(name)  # 404 if missing
        await self.repo.delete(name)
