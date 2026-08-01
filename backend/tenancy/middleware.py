"""ASGI middleware that binds a tenant to every request.

Written as raw ASGI rather than Starlette's ``BaseHTTPMiddleware`` on purpose:
``BaseHTTPMiddleware`` runs the downstream app in a child task, which makes
ContextVar propagation subtle. A plain ASGI wrapper sets the ContextVar in the
same task that awaits the app, so :func:`tenancy.context.current_tenant` is
reliable everywhere downstream.

Order of business per request:

1. Resolve the tenant from the ``Host`` header (respecting ``X-Forwarded-Host``
   from the reverse proxy).
2. Reject unknown tenants (404) and suspended ones (402/423) *before* auth runs
   — a suspended tenant should not be able to spend a database round trip.
3. Bind the tenant for the duration of the request and always unbind after.
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from integrations.control_plane import ControlPlaneError
from tenancy.context import (
    TenantContext,
    reset_current_tenant,
    set_current_tenant,
)
from tenancy.resolver import TenantResolver

# Paths served without a tenant: liveness probes and API docs. Everything else
# is tenant-scoped, including the unauthenticated branding endpoint.
_EXEMPT_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json", "/internal")

# Status codes chosen so a client can tell the states apart:
#   404 - no such tenant (wrong domain)
#   402 - suspended for billing; paying resolves it
#   423 - locked / provisioning; the tenant exists but is not servable yet
_SUSPENDED_STATUSES = {"suspended": 402, "provisioning": 423, "archived": 410}


class TenantMiddleware:
    def __init__(self, app: ASGIApp, resolver: TenantResolver) -> None:
        self.app = app
        self.resolver = resolver

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path.startswith(_EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return

        host = _request_host(scope)
        try:
            tenant = await self.resolver.resolve(host)
        except ControlPlaneError as exc:
            await _json(send, 503, f"Tenant directory unavailable: {exc}")
            return

        if tenant is None:
            await _json(send, 404, f"No workspace is configured for '{host}'.")
            return

        if not tenant.is_active:
            status = _SUSPENDED_STATUSES.get(tenant.status, 403)
            await _json(send, status, _suspension_detail(tenant))
            return

        scope.setdefault("state", {})["tenant"] = tenant
        token = set_current_tenant(tenant)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_current_tenant(token)


def _suspension_detail(tenant: TenantContext) -> str:
    if tenant.status == "suspended":
        return (
            f"The workspace '{tenant.name}' is suspended. "
            "Contact your administrator to restore access."
        )
    if tenant.status == "provisioning":
        return f"The workspace '{tenant.name}' is still being prepared."
    return f"The workspace '{tenant.name}' is no longer available."


def _request_host(scope: Scope) -> str:
    """Host for this request, preferring the proxy's forwarded value."""
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    forwarded = headers.get("x-forwarded-host")
    if forwarded:
        # May be a comma-separated chain; the first entry is the original host.
        return forwarded.split(",")[0].strip()
    return headers.get("host", "")


async def _json(send: Send, status: int, detail: str) -> None:
    """Emit a JSON error directly — we are below the app, so no Response reuse."""
    body = JSONResponse(status_code=status, content={"detail": detail}).body
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
