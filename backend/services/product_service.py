"""Product catalog business logic (proxying the ERPNext Item DocType)."""

from fastapi import HTTPException, status

from repositories.product_repository import ProductRepository
from schemas.product import ProductCreate, ProductRead, ProductUpdate


class ProductService:
    def __init__(self, repo: ProductRepository) -> None:
        self.repo = repo

    async def list(
        self,
        search: str | None = None,
        category: str | None = None,
        limit: int = 20,
        start: int = 0,
    ) -> list[ProductRead]:
        return await self.repo.list(search, category, limit, start)

    async def get(self, product_id: str) -> ProductRead:
        product = await self.repo.get(product_id)
        if product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
        return product

    async def create(self, data: ProductCreate) -> ProductRead:
        # The Item is identified by its SKU (item_code).
        if await self.repo.get(data.sku) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Product already exists")
        return await self.repo.create(data)

    async def update(self, product_id: str, data: ProductUpdate) -> ProductRead:
        await self.get(product_id)  # 404 if missing
        return await self.repo.update(product_id, data)

    async def delete(self, product_id: str) -> None:
        await self.get(product_id)  # 404 if missing
        await self.repo.delete(product_id)
