"""Per-tenant configuration for third-party integrations.

Today this holds mobile-money provider credentials; the shape is deliberately
generic (kind + provider + sealed blob) so WhatsApp and e-invoicing land here
too rather than each growing their own table.

**The tenant owns the merchant account, not us.** Credentials belong to the
customer's own CamPay / Fapshi / MTN account, funds settle directly to them,
and EquiMed never holds money. That is not a preference — holding customer
float would make this a licensed money-transmission business under CEMAC
banking regulation. See docs/payments.md.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.mixins import TenantScoped

# Integration families. One row per (tenant, kind, provider).
KIND_PAYMENT = "payment"

# Providers implemented in integrations/payments/.
PROVIDER_FAKE = "fake"
PROVIDER_CAMPAY = "campay"
PROVIDER_FAPSHI = "fapshi"
PROVIDER_MTN_MOMO = "mtn_momo"

PAYMENT_PROVIDERS = (
    PROVIDER_FAKE,
    PROVIDER_CAMPAY,
    PROVIDER_FAPSHI,
    PROVIDER_MTN_MOMO,
)

MODE_SANDBOX = "sandbox"
MODE_LIVE = "live"


class TenantIntegrationConfig(Base, TenantScoped):
    __tablename__ = "tenant_integration_config"
    # One configuration per provider per tenant. A tenant may keep both a
    # sandbox and a live provider row only by switching `mode`, which is
    # deliberate: two live rows for one provider invites paying from the wrong
    # account.
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "kind", "provider", name="uq_integration_tenant_kind_provider"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default=KIND_PAYMENT)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default=MODE_SANDBOX)

    # Only one provider per kind may be active for a tenant at a time; the
    # service enforces it so a collection cannot be routed ambiguously.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Fernet-sealed JSON. Shape differs per provider (see integrations/payments).
    credentials_enc: Mapped[str] = mapped_column(Text, default="")
    # Sealed separately: rotating a webhook secret should not require re-entering
    # the API credentials.
    webhook_secret_enc: Mapped[str] = mapped_column(Text, default="")

    # Non-secret provider options (payout service ids, default medium, whether
    # the merchant or the customer bears provider fees).
    settings_json: Mapped[str] = mapped_column(Text, default="{}")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
