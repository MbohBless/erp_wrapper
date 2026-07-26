"""Sales invoice schemas (Pydantic V2). Proxy over the ERPNext Sales Invoice DocType."""

from pydantic import BaseModel, Field


class InvoiceLineInput(BaseModel):
    item_code: str = Field(min_length=1, max_length=140)
    qty: float = Field(gt=0)
    rate: float = Field(ge=0)
    description: str | None = None


class SalesInvoiceCreate(BaseModel):
    customer: str = Field(min_length=1)
    items: list[InvoiceLineInput] = Field(min_length=1)
    due_date: str | None = None
    posting_date: str | None = None
    remarks: str | None = None
    update_stock: bool = False
    taxes_and_charges: str | None = None


class InvoiceLine(BaseModel):
    item_code: str
    qty: float
    rate: float
    amount: float


class SalesInvoiceRead(BaseModel):
    id: str
    customer: str
    posting_date: str | None = None
    due_date: str | None = None
    grand_total: float
    outstanding_amount: float
    status: str
    remarks: str | None = None
    items: list[InvoiceLine] = []
