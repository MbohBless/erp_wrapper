"""Shared ORM building blocks.

``TenantScoped`` is the marker that makes a table multi-tenant. Every app-owned
table carries it; the repositories filter on it and never expose an unscoped
query. Business data is untouched — that lives in ERPNext, which is isolated at
the site/database level instead.
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, declarative_mixin

from tenancy.context import DEFAULT_TENANT_ID


@declarative_mixin
class TenantScoped:
    """Adds the tenant discriminator column.

    Defaulting to ``DEFAULT_TENANT_ID`` keeps single-tenant (self-hosted)
    deployments and pre-existing rows working without a data migration.
    """

    tenant_id: Mapped[str] = mapped_column(
        String(64), index=True, nullable=False, default=DEFAULT_TENANT_ID
    )
