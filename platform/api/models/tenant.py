"""Tenant registry — the control plane's core record.

A ``Tenant`` row is the authoritative answer to three questions:

* does this hostname belong to anyone,
* is that workspace allowed to serve traffic right now, and
* which ERPNext site holds its business data.

``status`` is the on/off switch the tenant app enforces on every request.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

# Lifecycle. Only ACTIVE serves traffic; the tenant app maps the rest to a
# specific HTTP status so a customer sees why they are locked out.
STATUS_PENDING = "pending"
STATUS_PROVISIONING = "provisioning"
STATUS_ACTIVE = "active"
STATUS_SUSPENDED = "suspended"
STATUS_ARCHIVED = "archived"

TENANT_STATUSES = (
    STATUS_PENDING,
    STATUS_PROVISIONING,
    STATUS_ACTIVE,
    STATUS_SUSPENDED,
    STATUS_ARCHIVED,
)


class Tenant(Base):
    __tablename__ = "tenants"

    # Slug, not a surrogate int: it is the subdomain, the ERPNext site prefix
    # and the tenant_id written into every app-DB row. One stable identifier
    # across all three layers is worth more than an auto-increment.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_PENDING, index=True
    )
    plan_code: Mapped[str] = mapped_column(
        ForeignKey("plans.code", ondelete="RESTRICT"), nullable=False
    )

    contact_name: Mapped[str] = mapped_column(String(200), default="")
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    country: Mapped[str] = mapped_column(String(120), default="Cameroon")
    notes: Mapped[str] = mapped_column(Text, default="")

    # --- ERPNext coordinates --------------------------------------------
    # Dedicated instance: erpnext_url differs per tenant.
    # Shared bench:       erpnext_url is common, erpnext_site differs.
    erpnext_url: Mapped[str] = mapped_column(String(255), default="")
    erpnext_site: Mapped[str] = mapped_column(String(255), default="")
    erpnext_api_key: Mapped[str] = mapped_column(String(255), default="")
    # Encrypted at rest (see utils.crypto); never returned by the admin API.
    erpnext_api_secret_enc: Mapped[str] = mapped_column(Text, default="")

    # --- Lifecycle timestamps --------------------------------------------
    suspended_reason: Mapped[str] = mapped_column(String(255), default="")
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provisioned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    domains: Mapped[list["TenantDomain"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    @property
    def primary_host(self) -> str:
        for domain in self.domains:
            if domain.is_primary:
                return domain.host
        return self.domains[0].host if self.domains else ""


class TenantDomain(Base):
    """A hostname that routes to a tenant.

    Every tenant has one platform subdomain; customers on higher plans may add
    their own domain, which is what the Caddy on-demand-TLS check authorises.
    """

    __tablename__ = "tenant_domains"
    __table_args__ = (UniqueConstraint("host", name="uq_tenant_domain_host"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Set once the domain has been seen to resolve to us; the TLS authorisation
    # endpoint issues certificates for custom domains only after this.
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped[Tenant] = relationship(back_populates="domains")
