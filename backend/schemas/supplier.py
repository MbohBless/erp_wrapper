"""Supplier request/response schemas (Pydantic V2).

Maps the design-doc Supplier (name, contact, address, lead time) onto the
ERPNext "Supplier" DocType. Field <-> ERPNext mapping lives in
repositories/supplier_repository.py.
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

SupplierType = Literal["Company", "Individual"]


class SupplierBase(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    supplier_group: str = "All Supplier Groups"
    supplier_type: SupplierType = "Company"
    contact_person: str | None = Field(default=None, max_length=140)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    lead_time_days: int | None = Field(default=None, ge=0)
    tax_id: str | None = Field(default=None, max_length=60)
    disabled: bool = False


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=140)
    supplier_group: str | None = None
    supplier_type: SupplierType | None = None
    contact_person: str | None = Field(default=None, max_length=140)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    lead_time_days: int | None = Field(default=None, ge=0)
    tax_id: str | None = Field(default=None, max_length=60)
    disabled: bool | None = None


class SupplierRead(SupplierBase):
    # ERPNext document name (its primary identifier).
    id: str
