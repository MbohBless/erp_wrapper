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
    # A sale brokered by an agent and billed below the product's selling price.
    # The customer pays the lower figure and no payout is owed — the agent keeps
    # the spread — so this is a discount with a reason recorded against it, not
    # ERPNext's `sales_partner` commission. Without the reason, a deliberate
    # concession and a mistyped rate look identical a month later.
    is_commissioned: bool = False
    commission_agent: str | None = Field(default=None, max_length=140)


class SalesInvoiceUpdate(SalesInvoiceCreate):
    """Replaces a *posted* invoice wholesale.

    A submitted Sales Invoice is immutable in ERPNext, so this is applied as
    cancel-then-amend: every field is rewritten from this payload exactly as a
    create would write it, and an omitted field is cleared rather than kept.
    Same shape as SalesInvoiceCreate, named separately so the API contract says
    which one a route takes.
    """


class InvoiceLine(BaseModel):
    item_code: str
    # What the product's own selling price was when the invoice was raised
    # (ERPNext `price_list_rate`), against which `rate` is the amount actually
    # charged. The pair is what makes "how much did we give away" answerable;
    # None when the product had no price on file.
    list_rate: float | None = None
    # ERPNext copies the item's name onto the line when the invoice is saved, so
    # this is what the document was actually billed as — not today's catalogue
    # name. Optional because a list query never returns child rows at all.
    item_name: str | None = None
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
    # Round-tripped so an amendment can be posted without losing them. A PUT
    # replaces the whole document, so anything the write model accepts but the
    # read model hides is silently cleared by an edit — dropping the VAT
    # template off an invoice, or leaving stock issued against a cancelled one.
    update_stock: bool = False
    taxes_and_charges: str | None = None
    is_commissioned: bool = False
    commission_agent: str | None = None
    # Amendment lineage. `amended_from` names the cancelled invoice this one
    # replaces; `is_cancelled` marks an invoice that has been reversed and no
    # longer affects the ledger. Both are needed to decide whether an invoice
    # may still be edited, and by what — see SalesService.update.
    amended_from: str | None = None
    is_cancelled: bool = False
    is_opening: bool = False
