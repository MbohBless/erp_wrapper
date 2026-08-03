"""Turning an inbound request host into a :class:`TenantContext`.

Two implementations, chosen by ``TENANCY_MODE``:

``StaticTenantResolver`` (single)
    Self-hosted / dedicated instance. Always returns the one tenant configured
    in ``config.Settings``. The control plane is never contacted, so a customer
    running EquiMed on their own hardware has no dependency on our platform.

``ControlPlaneTenantResolver`` (multi)
    Shared SaaS plane. Asks the control plane to resolve the host, and caches
    the answer briefly. The cache TTL is also the upper bound on how long a
    suspension takes to take effect, so keep it small.
"""

import time
from typing import Protocol

from config import settings
from integrations.control_plane import ControlPlaneClient, ControlPlaneError
from tenancy.context import TenantContext

# Unknown hosts are cached for less time than real ones: a host that 404s today
# is usually a tenant that is about to be provisioned.
_NEGATIVE_TTL = 5.0

# Everything a self-hosted install is entitled to — which is everything. There
# is no plan to gate against when the customer runs the software themselves.
SELF_HOSTED_FEATURES = frozenset(
    {
        "branding",
        "dashboard_layout",
        "custom_domain",
        "reports",
        "budget",
        "dedicated_erp",
        "mobile_money",
    }
)


class TenantResolver(Protocol):
    async def resolve(self, host: str) -> TenantContext | None:
        """Return the tenant serving ``host``, or ``None`` if there is none."""
        ...


def _normalise_host(host: str) -> str:
    """Strip the port and lowercase — ``Client-A.equimed.app:443`` -> host."""
    return host.split(":", 1)[0].strip().lower()


class StaticTenantResolver:
    """Single-tenant mode: one tenant, built from environment configuration."""

    def __init__(self, tenant: TenantContext | None = None) -> None:
        self._tenant = tenant or TenantContext(
            id=settings.default_tenant_id,
            name=settings.default_tenant_name,
            status="active",
            plan="self-hosted",
            erpnext_url=settings.erpnext_url,
            erpnext_api_key=settings.erpnext_api_key,
            erpnext_api_secret=settings.erpnext_api_secret,
            # A self-hosted deployment has paid for everything it can run.
            # Keep in step with platform/api/models/plan.py::KNOWN_FEATURES —
            # a capability missing here is silently unavailable to every
            # self-hosted customer, which is a support ticket, not an error.
            features=SELF_HOSTED_FEATURES,
        )

    async def resolve(self, host: str) -> TenantContext | None:  # noqa: ARG002
        return self._tenant


class ControlPlaneTenantResolver:
    """Multi-tenant mode: resolve via the control plane, with a TTL cache."""

    def __init__(
        self,
        client: ControlPlaneClient | None = None,
        ttl: float | None = None,
    ) -> None:
        self._client = client or ControlPlaneClient()
        self._ttl = float(settings.tenant_cache_ttl if ttl is None else ttl)
        self._cache: dict[str, tuple[float, TenantContext | None]] = {}

    def invalidate(self, host: str | None = None) -> None:
        """Drop cached resolutions (all, or one host)."""
        if host is None:
            self._cache.clear()
        else:
            self._cache.pop(_normalise_host(host), None)

    async def resolve(self, host: str) -> TenantContext | None:
        key = _normalise_host(host)
        now = time.monotonic()

        cached = self._cache.get(key)
        if cached is not None and cached[0] > now:
            return cached[1]

        try:
            payload = await self._client.resolve_tenant(key)
        except ControlPlaneError:
            # Fail closed on an unknown host, but keep serving a host we have
            # already resolved: a control-plane blip must not take every tenant
            # offline. The stale entry is used only until the control plane
            # answers again.
            if cached is not None:
                return cached[1]
            raise

        tenant = _tenant_from_payload(payload) if payload else None
        ttl = self._ttl if tenant is not None else _NEGATIVE_TTL
        self._cache[key] = (now + ttl, tenant)
        return tenant


def _tenant_from_payload(payload: dict) -> TenantContext:
    return TenantContext(
        id=str(payload["id"]),
        name=payload.get("name") or str(payload["id"]),
        status=payload.get("status") or "active",
        plan=payload.get("plan") or "standard",
        erpnext_url=payload.get("erpnext_url") or settings.erpnext_url,
        erpnext_site=payload.get("erpnext_site") or None,
        erpnext_api_key=payload.get("erpnext_api_key") or "",
        erpnext_api_secret=payload.get("erpnext_api_secret") or "",
        features=frozenset(payload.get("features") or ()),
    )


def build_resolver() -> TenantResolver:
    """Pick the resolver matching the configured tenancy mode."""
    if settings.tenancy_mode == "multi":
        return ControlPlaneTenantResolver()
    return StaticTenantResolver()
