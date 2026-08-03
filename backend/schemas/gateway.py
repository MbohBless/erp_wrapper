"""Schemas for the mobile-money gateway.

Note what is *absent*: no response model ever carries a provider credential.
The settings UI shows which fields are configured, never their values.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.integration import MODE_LIVE, MODE_SANDBOX, PAYMENT_PROVIDERS

ProviderName = Literal["fake", "campay", "fapshi", "mtn_momo"]
Mode = Literal["sandbox", "live"]


# --- Provider configuration ----------------------------------------------
class ProviderConfigUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderName
    mode: Mode = MODE_SANDBOX
    # Omit to keep what is stored — the form never re-displays secrets, so it
    # must be able to save without them.
    credentials: dict[str, str] | None = None
    webhook_secret: str | None = None
    settings: dict[str, Any] | None = None
    activate: bool = False

    @field_validator("credentials")
    @classmethod
    def _strip(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return None
        return {k: str(val).strip() for k, val in v.items() if str(val).strip()}


class ProviderConfigRead(BaseModel):
    provider: str
    mode: str
    is_active: bool
    #: Credential field names that currently hold a value.
    configured_fields: list[str] = []
    #: Field names this provider requires, for rendering the form.
    required_fields: list[str] = []
    optional_fields: list[str] = []
    webhook_secret_set: bool = False
    supports_webhook_verification: bool = True
    settings: dict[str, Any] = {}
    updated_at: datetime | None = None


class ProviderCatalogEntry(BaseModel):
    provider: str
    required_fields: list[str]
    optional_fields: list[str]
    supports_webhook_verification: bool


# --- Intents ---------------------------------------------------------------
class CollectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: ERPNext Sales Invoice name. Omit for an unattached collection.
    invoice_id: str | None = None
    #: Whole currency units. Omitted means "whatever is still outstanding".
    amount: Annotated[int, Field(ge=1)] | None = None
    payer_msisdn: str = ""
    payer_name: str = ""
    payer_email: str = ""
    description: Annotated[str, Field(max_length=255)] = ""
    #: Hosted checkout link instead of prompting a handset directly.
    hosted: bool = False
    redirect_url: str = ""
    #: Charge again even though an attempt is already in flight for this
    #: invoice. Needed for genuine instalments; off by default so a double
    #: click cannot take money twice.
    force: bool = False


class PayoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: ERPNext Purchase Invoice name. Omit for an unattached payout.
    bill_id: str | None = None
    amount: Annotated[int, Field(ge=1)] | None = None
    payee_msisdn: str
    payee_name: str = ""
    payee_email: str = ""
    description: Annotated[str, Field(max_length=255)] = ""
    force: bool = False


class PaymentIntentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: str
    direction: str
    provider: str
    mode: str
    amount: int
    currency: str
    counterparty_msisdn: str
    counterparty_name: str
    description: str
    erpnext_doctype: str
    erpnext_docname: str
    erpnext_payment_entry: str
    status: str
    reconciliation: str
    failure_reason: str
    review_reason: str
    provider_ref: str
    provider_status: str
    operator: str
    operator_ref: str
    payment_url: str
    ussd_code: str
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None


class SweepResult(BaseModel):
    """Outcome of polling every in-flight intent."""

    checked: int
    settled: int
    posted: int
    needs_review: int
    still_pending: int
    errors: list[str] = []


class WebhookAck(BaseModel):
    """Deliberately uninformative.

    Callback endpoints are unauthenticated, so the response must not tell a
    prober whether a reference exists or what state it is in.
    """

    received: bool = True


__all__ = [
    "MODE_LIVE",
    "MODE_SANDBOX",
    "PAYMENT_PROVIDERS",
    "CollectionCreate",
    "PaymentIntentRead",
    "PayoutCreate",
    "ProviderCatalogEntry",
    "ProviderConfigRead",
    "ProviderConfigUpsert",
    "SweepResult",
    "WebhookAck",
]
