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
    remarks: str | None = None


class PurchaseInvoiceUpdate(PurchaseInvoiceCreate):
    """Replaces a *posted* supplier bill wholesale.

    A submitted Purchase Invoice is immutable in ERPNext, so this is applied as
    cancel-then-amend: every field is rewritten from this payload exactly as a
    create would write it, and an omitted field is cleared rather than kept.
    """


class BillLine(BaseModel):
    item_code: str
    item_name: str | None = None  # as billed; see InvoiceLine in schemas/sales.py
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
    remarks: str | None = None
    items: list[BillLine] = []
    # See schemas/sales.py for what these three carry — the amendment lineage
    # is identical on both invoice types.
    amended_from: str | None = None
    is_cancelled: bool = False
    is_opening: bool = False
