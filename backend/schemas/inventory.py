"""Inventory schemas (Pydantic V2).

Maps onto ERPNext DocTypes:
  - Warehouse    -> warehouses
  - Batch        -> batch numbers + expiry dates
  - Bin          -> product stock levels (read-only, computed by ERPNext)
  - Stock Entry  -> goods received (Material Receipt) / goods issued (Material Issue)
Field mappings live in the corresponding repositories.
"""

from datetime import date

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- Warehouse


class WarehouseBase(BaseModel):
    name: str = Field(min_length=1, max_length=140)  # -> warehouse_name
    parent_warehouse: str | None = None
    is_group: bool = False
    disabled: bool = False


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=140)
    parent_warehouse: str | None = None
    is_group: bool | None = None
    disabled: bool | None = None


class WarehouseRead(WarehouseBase):
    id: str  # ERPNext Warehouse name


# -------------------------------------------------------------------- Batch


class BatchBase(BaseModel):
    batch_id: str = Field(min_length=1, max_length=140)
    item_code: str = Field(min_length=1, max_length=140)  # -> item
    expiry_date: date | None = None
    manufacturing_date: date | None = None


class BatchCreate(BatchBase):
    pass


class BatchRead(BatchBase):
    id: str
    qty: float | None = None  # batch_qty (computed)


# --------------------------------------------------------------- Stock level


class StockLevel(BaseModel):
    item_code: str
    warehouse: str
    actual_qty: float = 0
    reserved_qty: float | None = None
    projected_qty: float | None = None


# ------------------------------------------------------- Goods movements


class MovementLine(BaseModel):
    item_code: str = Field(min_length=1, max_length=140)
    qty: float = Field(gt=0)
    batch_no: str | None = None
    rate: float | None = Field(default=None, ge=0)  # basic_rate (receipts)


class GoodsReceiptRequest(BaseModel):
    """Goods Received -> ERPNext Stock Entry (Material Receipt)."""

    warehouse: str = Field(min_length=1)  # target warehouse
    items: list[MovementLine] = Field(min_length=1)


class GoodsIssueRequest(BaseModel):
    """Goods Issued -> ERPNext Stock Entry (Material Issue)."""

    warehouse: str = Field(min_length=1)  # source warehouse
    items: list[MovementLine] = Field(min_length=1)


class StockEntryLine(BaseModel):
    item_code: str
    qty: float
    warehouse: str | None = None
    batch_no: str | None = None


class StockEntryRead(BaseModel):
    id: str
    stock_entry_type: str
    items: list[StockEntryLine]
