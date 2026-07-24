"""Product request/response schemas (Pydantic V2).

Maps the design-doc Product onto the ERPNext "Item" DocType. Field <-> ERPNext
mapping lives in repositories/product_repository.py.
"""

from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=140)  # -> item_name
    sku: str = Field(min_length=1, max_length=140)  # -> item_code (identifier)
    barcode: str | None = Field(default=None, max_length=140)
    category: str = "All Item Groups"  # -> item_group
    manufacturer: str | None = Field(default=None, max_length=140)
    purchase_price: float | None = Field(default=None, ge=0)
    selling_price: float | None = Field(default=None, ge=0)
    unit: str = "Nos"  # -> stock_uom
    image: str | None = Field(default=None, max_length=500)
    disabled: bool = False


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=140)
    sku: str | None = Field(default=None, min_length=1, max_length=140)
    barcode: str | None = Field(default=None, max_length=140)
    category: str | None = None
    manufacturer: str | None = Field(default=None, max_length=140)
    purchase_price: float | None = Field(default=None, ge=0)
    selling_price: float | None = Field(default=None, ge=0)
    unit: str | None = None
    image: str | None = Field(default=None, max_length=500)
    disabled: bool | None = None


class ProductRead(ProductBase):
    # ERPNext document name (== item_code).
    id: str
