"""Tenant isolation: context, resolution and request binding.

Cross-cutting infrastructure (like ``utils/``), sitting beside the strict
api -> services -> repositories layering rather than inside it. Import the
public names from here, not from the submodules.
"""

from tenancy.context import (
    DEFAULT_TENANT_ID,
    TenantContext,
    TenantNotResolved,
    current_tenant,
    current_tenant_id,
    current_tenant_or_none,
    reset_current_tenant,
    set_current_tenant,
)
from tenancy.middleware import TenantMiddleware
from tenancy.resolver import (
    ControlPlaneTenantResolver,
    StaticTenantResolver,
    TenantResolver,
    build_resolver,
)

__all__ = [
    "DEFAULT_TENANT_ID",
    "ControlPlaneTenantResolver",
    "StaticTenantResolver",
    "TenantContext",
    "TenantMiddleware",
    "TenantNotResolved",
    "TenantResolver",
    "build_resolver",
    "current_tenant",
    "current_tenant_id",
    "current_tenant_or_none",
    "reset_current_tenant",
    "set_current_tenant",
]
