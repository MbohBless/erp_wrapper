"""Company profile ORM model — the tenant's *legal* identity.

App-owned configuration (not business data): drives the branded letterhead and
signatory block on generated PDF reports. One row per tenant.

Kept deliberately separate from ``models.branding.TenantBranding``, which owns
the tenant's *application skin*. They are different concerns with different
editors and different assets: a print letterhead is not a UI theme.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.mixins import TenantScoped


class CompanyProfile(Base, TenantScoped):
    __tablename__ = "company_profile"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_company_profile_tenant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    display_name: Mapped[str] = mapped_column(String(160), default="")
    legal_name: Mapped[str] = mapped_column(String(200), default="")
    tagline: Mapped[str] = mapped_column(String(200), default="Medical Equipment Distribution")

    address_line: Mapped[str] = mapped_column(String(255), default="")
    city: Mapped[str] = mapped_column(String(120), default="Douala")
    country: Mapped[str] = mapped_column(String(120), default="Cameroon")
    phone: Mapped[str] = mapped_column(String(80), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    website: Mapped[str] = mapped_column(String(160), default="")

    # Legal identifiers (Cameroon: RC = Registre de Commerce, NIU = tax id).
    rc_number: Mapped[str] = mapped_column(String(120), default="")
    niu: Mapped[str] = mapped_column(String(120), default="")
    currency: Mapped[str] = mapped_column(String(12), default="XAF")

    # Signatory printed under the digital-signature block.
    signatory_name: Mapped[str] = mapped_column(String(160), default="")
    signatory_title: Mapped[str] = mapped_column(String(160), default="Authorized Signatory")

    accent_color: Mapped[str] = mapped_column(String(9), default="#416180")
    # Optional logo as a data: URI (data:image/png;base64,...). TEXT for size.
    logo_data_url: Mapped[str] = mapped_column(Text, default="")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
