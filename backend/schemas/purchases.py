"""Purchase invoice schemas (Pydantic V2). Proxy over the ERPNext Purchase Invoice DocType."""

from pydantic import BaseModel, Field


class BillLineInput(BaseModel):
    item_code: str = Field(min_length=1, max_length=140)
    qty: float = Field(gt=0)
    rate: float = Field(ge=0)


class PurchaseInvoiceCreate(BaseModel):
    supplier: str = Field(min_length=1)
    items: list[BillLineInput] = Field(min_length=1)
    bill_no: str | None = None
    posting_date: str | None = None


class BillLine(BaseModel):
    item_code: str
    qty: float
    rate: float
    amount: float


class PurchaseInvoiceRead(BaseModel):
    id: str
    supplier: str
    posting_date: str | None = None
    due_date: str | None = None
    bill_no: str | None = None
    grand_total: float
    outstanding_amount: float
    status: str
    items: list[BillLine] = []
