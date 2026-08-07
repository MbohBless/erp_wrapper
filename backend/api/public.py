"""Unauthenticated, tenant-scoped endpoints.

Only branding lives here, and only the subset needed to paint a sign-in screen.
The route is still behind ``TenantMiddleware``, so an unknown host 404s and a
suspended workspace is refused before anything is read — but it is deliberately
outside the auth dependency, because a user has to see whose login page they
are on *before* they have a token.
"""

from fastapi import APIRouter, Depends, Response

from api.deps import get_branding_service, get_tenant
from schemas.branding import PublicBranding
from services.branding_service import BrandingService
from tenancy import TenantContext

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/branding", response_model=PublicBranding)
def public_branding(
    response: Response,
    service: BrandingService = Depends(get_branding_service),
    tenant: TenantContext = Depends(get_tenant),
) -> PublicBranding:
    # Explicitly uncacheable. Without this a browser may heuristically cache the
    # 200 (there is no Cache-Control, no ETag, no Last-Modified), and a tenant
    # who rebrands keeps seeing the old name until they clear their cache —
    # which is exactly how this was found.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return service.public(tenant.id)
