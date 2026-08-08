"""Inventory business logic: warehouses, batches, stock levels, goods movements."""

from fastapi import HTTPException, status

from repositories.batch_repository import BatchRepository
from repositories.product_repository import ProductRepository
from repositories.stock_entry_repository import StockEntryRepository
from repositories.stock_repository import StockRepository
from repositories.warehouse_repository import WarehouseRepository
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


class InventoryService:
    def __init__(
        self,
        warehouses: WarehouseRepository,
        batches: BatchRepository,
        stock: StockRepository,
        stock_entries: StockEntryRepository,
        products: ProductRepository,
    ) -> None:
        self.warehouses = warehouses
        self.batches = batches
        self.stock = stock
        self.stock_entries = stock_entries
        # Batches need to check the item is batch-tracked before ERPNext is
        # asked to create one.
        self.products = products

    # -- Warehouses ---------------------------------------------------------
    async def list_warehouses(self, limit: int = 50, start: int = 0) -> list[WarehouseRead]:
        return await self.warehouses.list(limit, start)

    async def get_warehouse(self, warehouse_id: str) -> WarehouseRead:
        warehouse = await self.warehouses.get(warehouse_id)
        if warehouse is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Warehouse not found")
        return warehouse

    async def create_warehouse(self, data: WarehouseCreate) -> WarehouseRead:
        return await self.warehouses.create(data)

    async def update_warehouse(
        self, warehouse_id: str, data: WarehouseUpdate
    ) -> WarehouseRead:
        await self.get_warehouse(warehouse_id)
        return await self.warehouses.update(warehouse_id, data)

    async def delete_warehouse(self, warehouse_id: str) -> None:
        await self.get_warehouse(warehouse_id)
        await self.warehouses.delete(warehouse_id)

    # -- Batches ------------------------------------------------------------
    async def list_batches(self, limit: int = 50, start: int = 0) -> list[BatchRead]:
        return await self.batches.list(limit, start)

    async def get_batch(self, batch_id: str) -> BatchRead:
        batch = await self.batches.get(batch_id)
        if batch is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
        return batch

    async def create_batch(self, data: BatchCreate) -> BatchRead:
        if await self.batches.get(data.batch_id) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Batch already exists")

        # Check the item before handing it to ERPNext. Left to ERPNext, an
        # unknown item_code came back as a 500 ("cannot unpack non-iterable
        # NoneType") and an item without batch tracking as a bare "The selected
        # item cannot have Batch" — neither of which tells the user what to do.
        product = await self.products.get(data.item_code)
        if product is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"No product with SKU '{data.item_code}'.",
            )
        if not product.track_batches:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"'{data.item_code}' is not batch-tracked. Enable batch tracking "
                "on the product first — ERPNext cannot add it once the item has "
                "stock movements.",
            )
        return await self.batches.create(data)

    # -- Stock levels -------------------------------------------------------
    async def get_stock_levels(
        self,
        item_code: str | None = None,
        warehouse: str | None = None,
        limit: int = 50,
        start: int = 0,
    ) -> list[StockLevel]:
        return await self.stock.list(item_code, warehouse, limit, start)

    # -- Goods movements ----------------------------------------------------
    async def receive_goods(self, req: GoodsReceiptRequest) -> StockEntryRead:
        return await self.stock_entries.create_receipt(req)

    async def issue_goods(self, req: GoodsIssueRequest) -> StockEntryRead:
        return await self.stock_entries.create_issue(req)
