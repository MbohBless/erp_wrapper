"""Product catalog business logic (proxying the ERPNext Item DocType)."""

from fastapi import HTTPException, status

from repositories.product_repository import ProductRepository
from schemas.product import ProductCreate, ProductRead, ProductUpdate
from services.reference_service import ReferenceService

# ERPNext tree roots. Selectable-looking, never selectable.
_GROUP_ROOTS = {"All Item Groups"}


class ProductService:
    def __init__(
        self, repo: ProductRepository, reference: ReferenceService | None = None
    ) -> None:
        self.repo = repo
        self.reference = reference

    async def _usable_category(self, given: str | None) -> str | None:
        """Turn an unusable item group into one ERPNext will accept.

        Mirrors CustomerService._usable_group, and for the same reason: the tree
        root cannot be selected, and neither can an empty value. Both arrive
        from a caller that never made a real choice, so substituting a
        selectable category beats refusing over a field nobody touched.

        An explicitly chosen leaf is always left alone.
        """
        if given and given not in _GROUP_ROOTS:
            return given
        if self.reference is None:
            return None if given in _GROUP_ROOTS else given
        # None, not the root — see CustomerService._usable_group.
        return await self.reference.default_item_group() or None

    async def list(
        self,
        search: str | None = None,
        category: str | None = None,
        disabled: bool | None = None,
        limit: int = 20,
        start: int = 0,
    ) -> list[ProductRead]:
        return await self.repo.list(search, category, disabled, limit, start)

    async def get(self, product_id: str) -> ProductRead:
        product = await self.repo.get(product_id)
        if product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
        return product

    async def create(self, data: ProductCreate) -> ProductRead:
        # The Item is identified by its SKU (item_code).
        if await self.repo.get(data.sku) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Product already exists")
        data = data.model_copy(
            update={"category": await self._usable_category(data.category)}
        )
        return await self.repo.create(data)

    async def update(self, product_id: str, data: ProductUpdate) -> ProductRead:
        await self.get(product_id)  # 404 if missing
        if data.category is not None:
            data = data.model_copy(
                update={"category": await self._usable_category(data.category)}
            )
        return await self.repo.update(product_id, data)

    async def delete(self, product_id: str) -> None:
        await self.get(product_id)  # 404 if missing
        await self.repo.delete(product_id)
