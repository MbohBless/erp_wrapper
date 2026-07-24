"""Inventory endpoints with RBAC. Thin controllers — logic lives in InventoryService.

Access policy (Administrator is always allowed):
  - view (stock/warehouses/batches read):  Manager, Store Keeper, Accountant, Sales
  - manage (warehouse/batch write, goods movements):  Manager, Store Keeper
"""

from fastapi import APIRouter, Depends, status

from api.deps import get_inventory_service, require_roles
from models.user import Role
from schemas.inventory import (
    BatchCreate,
    BatchRead,
    GoodsIssueRequest,
    GoodsReceiptRequest,
    StockEntryRead,
    StockLevel,
    WarehouseCreate,
    WarehouseRead,
    WarehouseUpdate,
)
from services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["inventory"])

can_view = require_roles(
    Role.MANAGER, Role.STORE_KEEPER, Role.ACCOUNTANT, Role.SALES
)
can_manage = require_roles(Role.MANAGER, Role.STORE_KEEPER)


# ------------------------------------------------------------- Warehouses
@router.get(
    "/warehouses", response_model=list[WarehouseRead], dependencies=[Depends(can_view)]
)
async def list_warehouses(
    limit: int = 50,
    start: int = 0,
    service: InventoryService = Depends(get_inventory_service),
) -> list[WarehouseRead]:
    return await service.list_warehouses(limit, start)


@router.post(
    "/warehouses",
    response_model=WarehouseRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def create_warehouse(
    data: WarehouseCreate,
    service: InventoryService = Depends(get_inventory_service),
) -> WarehouseRead:
    return await service.create_warehouse(data)


@router.get(
    "/warehouses/{warehouse_id}",
    response_model=WarehouseRead,
    dependencies=[Depends(can_view)],
)
async def get_warehouse(
    warehouse_id: str,
    service: InventoryService = Depends(get_inventory_service),
) -> WarehouseRead:
    return await service.get_warehouse(warehouse_id)


@router.put(
    "/warehouses/{warehouse_id}",
    response_model=WarehouseRead,
    dependencies=[Depends(can_manage)],
)
async def update_warehouse(
    warehouse_id: str,
    data: WarehouseUpdate,
    service: InventoryService = Depends(get_inventory_service),
) -> WarehouseRead:
    return await service.update_warehouse(warehouse_id, data)


@router.delete(
    "/warehouses/{warehouse_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(can_manage)],
)
async def delete_warehouse(
    warehouse_id: str,
    service: InventoryService = Depends(get_inventory_service),
) -> None:
    await service.delete_warehouse(warehouse_id)


# ----------------------------------------------------------------- Batches
@router.get(
    "/batches", response_model=list[BatchRead], dependencies=[Depends(can_view)]
)
async def list_batches(
    limit: int = 50,
    start: int = 0,
    service: InventoryService = Depends(get_inventory_service),
) -> list[BatchRead]:
    return await service.list_batches(limit, start)


@router.post(
    "/batches",
    response_model=BatchRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def create_batch(
    data: BatchCreate,
    service: InventoryService = Depends(get_inventory_service),
) -> BatchRead:
    return await service.create_batch(data)


@router.get(
    "/batches/{batch_id}", response_model=BatchRead, dependencies=[Depends(can_view)]
)
async def get_batch(
    batch_id: str,
    service: InventoryService = Depends(get_inventory_service),
) -> BatchRead:
    return await service.get_batch(batch_id)


# ------------------------------------------------------------- Stock levels
@router.get(
    "/stock", response_model=list[StockLevel], dependencies=[Depends(can_view)]
)
async def stock_levels(
    item_code: str | None = None,
    warehouse: str | None = None,
    limit: int = 50,
    start: int = 0,
    service: InventoryService = Depends(get_inventory_service),
) -> list[StockLevel]:
    return await service.get_stock_levels(item_code, warehouse, limit, start)


# --------------------------------------------------------- Goods movements
@router.post(
    "/receive",
    response_model=StockEntryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def receive_goods(
    data: GoodsReceiptRequest,
    service: InventoryService = Depends(get_inventory_service),
) -> StockEntryRead:
    return await service.receive_goods(data)


@router.post(
    "/issue",
    response_model=StockEntryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def issue_goods(
    data: GoodsIssueRequest,
    service: InventoryService = Depends(get_inventory_service),
) -> StockEntryRead:
    return await service.issue_goods(data)
