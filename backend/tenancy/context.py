"""Per-request tenant identity.

The tenant is resolved once per request by :mod:`tenancy.middleware` and stashed
in a :class:`~contextvars.ContextVar` so that dependencies deep in the stack
(the ERPNext client factory, the app-DB repositories) can read it without every
router threading it through by hand.

Reading the tenant is *always* done through :func:`current_tenant` or
:func:`current_tenant_id`. Nothing else may touch the ContextVar directly — that
single accessor is what makes tenant isolation auditable.
"""

from contextvars import ContextVar, Token
from dataclasses import dataclass, field

# Identifier used for the implicit tenant in single-tenant (self-hosted) mode.
DEFAULT_TENANT_ID = "default"


class TenantNotResolved(RuntimeError):
    """Raised when tenant-scoped code runs outside a tenant-resolved request."""


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Everything the tenant app needs to serve one customer.

    Deliberately carries the ERPNext coordinates as data rather than reading
    them from global settings: that is what lets one process serve many tenants
    (SaaS) and one process serve exactly one (self-hosted) with the same code.

    ``erpnext_site`` supports the Frappe multi-site deployment: a shared bench
    resolves the site from the HTTP ``Host`` header, so many tenants share one
    ``erpnext_url`` but each gets its own database.
    """

    id: str
    name: str
    status: str = "active"
    plan: str = "standard"
    erpnext_url: str = ""
    erpnext_site: str | None = None
    erpnext_api_key: str = ""
    erpnext_api_secret: str = ""
    features: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def has_feature(self, name: str) -> bool:
        return name in self.features


_tenant_var: ContextVar[TenantContext | None] = ContextVar("equimed_tenant", default=None)


def set_current_tenant(tenant: TenantContext | None) -> Token:
    """Bind the tenant for the current context. Returns a reset token."""
    return _tenant_var.set(tenant)


def reset_current_tenant(token: Token) -> None:
    _tenant_var.reset(token)


def current_tenant_or_none() -> TenantContext | None:
    return _tenant_var.get()


def current_tenant() -> TenantContext:
    """Return the active tenant, or raise if the request was not scoped."""
    tenant = _tenant_var.get()
    if tenant is None:
        raise TenantNotResolved(
            "No tenant bound to this request. Tenant-scoped code must run "
            "behind TenantMiddleware."
        )
    return tenant


def current_tenant_id() -> str:
    return current_tenant().id
