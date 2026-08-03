"""A single attempt to move money through a mobile-money provider.

One row per collection (customer pays us) or payout (we pay a supplier). It is
the durable record that survives provider timeouts, duplicate webhooks and
process restarts — the provider's own reference is *not* enough, because it does
not exist yet at the moment we decide to charge someone.

Two independent state axes, deliberately not collapsed into one:

``status``        did the money move?          created → pending → succeeded/failed/expired
``reconciliation`` did we post it to the ledger?  pending → posted / needs_review / not_applicable

They are separate because a payment can succeed while posting to ERPNext fails
(ERPNext down, invoice already closed, amount mismatch). Collapsing them would
either lose a real payment or double-post it, and both are worse than a row that
says "money arrived, ledger entry still owed".
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.mixins import TenantScoped

DIRECTION_COLLECTION = "collection"  # money in
DIRECTION_PAYOUT = "payout"  # money out

STATUS_CREATED = "created"
STATUS_PENDING = "pending"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_EXPIRED = "expired"

TERMINAL_STATUSES = (STATUS_SUCCEEDED, STATUS_FAILED, STATUS_EXPIRED)

RECON_PENDING = "pending"
RECON_POSTED = "posted"
RECON_NEEDS_REVIEW = "needs_review"
RECON_NOT_APPLICABLE = "not_applicable"


class PaymentIntent(Base, TenantScoped):
    __tablename__ = "payment_intent"
    # `reference` is ours and is what we send to the provider as their external
    # id, so it must be unique per tenant. It is also the idempotency key for
    # "charge this invoice" — retrying with the same reference must not create
    # a second charge.
    __table_args__ = (
        UniqueConstraint("tenant_id", "reference", name="uq_payment_intent_reference"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    reference: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="sandbox")

    # XAF is a zero-decimal currency: there are no centimes. Amounts are whole
    # units, stored as an integer so no float rounding can ever reach the ledger.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="XAF")

    # Payer (collection) or payee (payout), in international format: 2376XXXXXXXX.
    counterparty_msisdn: Mapped[str] = mapped_column(String(24), default="")
    counterparty_name: Mapped[str] = mapped_column(String(160), default="")
    description: Mapped[str] = mapped_column(String(255), default="")

    # What this pays for. `erpnext_doctype` is "Sales Invoice" for collections
    # and "Purchase Invoice" for payouts; blank for an unattached payment.
    erpnext_doctype: Mapped[str] = mapped_column(String(60), default="")
    erpnext_docname: Mapped[str] = mapped_column(String(140), default="", index=True)
    # The Payment Entry we created once the money was confirmed.
    erpnext_payment_entry: Mapped[str] = mapped_column(String(140), default="")

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STATUS_CREATED, index=True
    )
    reconciliation: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RECON_PENDING, index=True
    )
    # Why a payment failed, or why reconciliation needs a human.
    failure_reason: Mapped[str] = mapped_column(String(255), default="")
    review_reason: Mapped[str] = mapped_column(String(255), default="")

    # Provider-side identifiers.
    provider_ref: Mapped[str] = mapped_column(String(140), default="", index=True)
    provider_status: Mapped[str] = mapped_column(String(40), default="")
    operator: Mapped[str] = mapped_column(String(40), default="")
    operator_ref: Mapped[str] = mapped_column(String(140), default="")
    # Hosted checkout URL / USSD prompt returned at initiation, if any.
    payment_url: Mapped[str] = mapped_column(Text, default="")
    ussd_code: Mapped[str] = mapped_column(String(64), default="")

    # Last raw provider response, for support and for reconstructing history
    # when a provider changes its payload shape.
    last_payload: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def needs_posting(self) -> bool:
        """Money arrived but the ledger entry is still owed."""
        return (
            self.status == STATUS_SUCCEEDED
            and self.reconciliation == RECON_PENDING
            and bool(self.erpnext_docname)
        )
