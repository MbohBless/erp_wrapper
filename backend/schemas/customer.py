"""Customer request/response schemas (Pydantic V2).

Maps the design-doc Customer onto the ERPNext "Customer" DocType. Field <-> ERPNext
mapping lives in repositories/customer_repository.py.
"""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

CustomerType = Literal["Company", "Individual"]


class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    customer_group: str = "All Customer Groups"
    customer_type: CustomerType = "Company"
    territory: str = "All Territories"
    contact_person: str | None = Field(default=None, max_length=140)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    tax_id: str | None = Field(default=None, max_length=60)
    disabled: bool = False


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=140)
    customer_group: str | None = None
    customer_type: CustomerType | None = None
    territory: str | None = None
    contact_person: str | None = Field(default=None, max_length=140)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    tax_id: str | None = Field(default=None, max_length=60)
    disabled: bool | None = None


class CustomerRead(CustomerBase):
    id: str  # ERPNext document name
    outstanding_balance: float | None = None  # receivables (read-only)
