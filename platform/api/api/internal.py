"""Machine-to-machine endpoints.

Two consumers, both on the internal network:

``/internal/tenants/resolve``
    The tenant app, on every cold request. The hottest endpoint in the platform
    and the only place ERPNext credentials are handed out — so it requires the
    shared secret.

``/internal/tls/check``
    Caddy's on-demand-TLS ask endpoint. Caddy cannot attach custom headers, so
    this one is unauthenticated by necessity; it is safe because it answers a
    single yes/no about a hostname whose existence is already observable in DNS,
    and reveals nothing about the tenant behind it.

Never route this prefix through the public reverse proxy.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.deps import get_internal_tenant_service, require_internal_token
from schemas.tenant import ResolvedTenant
from services.tenant_service import TenantService

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get(
    "/tenants/resolve",
    response_model=ResolvedTenant,
    dependencies=[Depends(require_internal_token)],
)
def resolve_tenant(
    host: str = Query(description="Request host, without port"),
    service: TenantService = Depends(get_internal_tenant_service),
) -> ResolvedTenant:
    resolved = service.resolve(host)
    if resolved is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No tenant for host '{host}'")
    return resolved


@router.get("/tls/check")
def tls_check(
    domain: str = Query(description="Hostname Caddy wants a certificate for"),
    service: TenantService = Depends(get_internal_tenant_service),
) -> Response:
    """Answer Caddy's on-demand TLS question for ``domain``.

    200 = issue a certificate, 403 = refuse. Only known, verified, non-archived
    tenant domains qualify, so pointing DNS at us is not enough to make us
    request certificates on someone else's behalf.
    """
    if service.authorize_tls(domain):
        return Response(status_code=status.HTTP_200_OK)
    return Response(status_code=status.HTTP_403_FORBIDDEN)
