"""Payment schemas (Pydantic V2). Proxy over the ERPNext Payment Entry DocType."""

from pydantic import BaseModel, Field


class PaymentReceive(BaseModel):
    """Record a customer receipt against a Sales Invoice."""

    invoice_id: str = Field(min_length=1)
    amount: float | None = Field(default=None, gt=0)  # defaults to full outstanding
    mode_of_payment: str | None = None
    posting_date: str | None = None
    reference_no: str | None = None


class PaymentPay(BaseModel):
    """Record a supplier payment against a Purchase Invoice."""

    bill_id: str = Field(min_length=1)
    amount: float | None = Field(default=None, gt=0)
    mode_of_payment: str | None = None
    posting_date: str | None = None
    reference_no: str | None = None


class PaymentRead(BaseModel):
    id: str
    payment_type: str | None = None
    party_type: str | None = None
    party: str | None = None
    paid_amount: float
    posting_date: str | None = None
    mode_of_payment: str | None = None
    reference_no: str | None = None
