"""Product endpoints with RBAC. Thin controllers — logic lives in ProductService.

Access policy (Administrator is always allowed):
  - view (list/get):   any authenticated user (the catalog is needed everywhere)
  - manage (write):    Manager
"""

from fastapi import APIRouter, Depends, status

from api.deps import get_current_user, get_product_service, require_roles
from models.user import Role
from schemas.product import ProductCreate, ProductRead, ProductUpdate
from services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])

can_manage = require_roles(Role.MANAGER)


@router.get(
    "", response_model=list[ProductRead], dependencies=[Depends(get_current_user)]
)
async def list_products(
    search: str | None = None,
    category: str | None = None,
    disabled: bool | None = None,
    limit: int = 20,
    start: int = 0,
    service: ProductService = Depends(get_product_service),
) -> list[ProductRead]:
    return await service.list(search, category, disabled, limit, start)


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def create_product(
    data: ProductCreate,
    service: ProductService = Depends(get_product_service),
) -> ProductRead:
    return await service.create(data)


@router.get(
    "/{product_id}",
    response_model=ProductRead,
    dependencies=[Depends(get_current_user)],
)
async def get_product(
    product_id: str,
    service: ProductService = Depends(get_product_service),
) -> ProductRead:
    return await service.get(product_id)


@router.put(
    "/{product_id}", response_model=ProductRead, dependencies=[Depends(can_manage)]
)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    service: ProductService = Depends(get_product_service),
) -> ProductRead:
    return await service.update(product_id, data)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(can_manage)],
)
async def delete_product(
    product_id: str,
    service: ProductService = Depends(get_product_service),
) -> None:
    await service.delete(product_id)
