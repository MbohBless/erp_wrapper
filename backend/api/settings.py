"""Settings endpoints: company profile (PDF letterhead) and tenant branding.

Two distinct resources on purpose:

``/settings/company-profile``
    The tenant's legal identity — legal name, address, RC/NIU, signatory. Drives
    generated PDFs.

``/settings/branding``
    The tenant's application skin — product name, logos, theme tokens, dashboard
    layout. Gated on the ``branding`` plan feature so white-labelling can be a
    paid capability on the SaaS plane (self-hosted tenants always have it).

Access (Administrator always allowed):
  - read: any authenticated user (needed to render the UI).
  - update: Manager, Accountant.
"""

from fastapi import APIRouter, Depends

from api.deps import (
    get_branding_service,
    get_company_service,
    get_current_user,
    require_feature,
    require_roles,
)
from models.user import Role
from schemas.branding import BrandingRead, BrandingUpdate, DashboardLayout
from schemas.company import CompanyProfileRead, CompanyProfileUpdate
from services.branding_service import BrandingService
from services.company_service import CompanyService

router = APIRouter(prefix="/settings", tags=["settings"])

can_edit = require_roles(Role.MANAGER, Role.ACCOUNTANT)
has_branding = require_feature("branding")
has_dashboard_layout = require_feature("dashboard_layout")


@router.get(
    "/company-profile",
    response_model=CompanyProfileRead,
    dependencies=[Depends(get_current_user)],
)
def get_company_profile(
    service: CompanyService = Depends(get_company_service),
) -> CompanyProfileRead:
    return service.get_profile()


@router.put(
    "/company-profile",
    response_model=CompanyProfileRead,
    dependencies=[Depends(can_edit)],
)
def update_company_profile(
    data: CompanyProfileUpdate,
    service: CompanyService = Depends(get_company_service),
) -> CompanyProfileRead:
    return service.update_profile(data)


@router.get(
    "/branding",
    response_model=BrandingRead,
    dependencies=[Depends(get_current_user)],
)
def get_branding(service: BrandingService = Depends(get_branding_service)) -> BrandingRead:
    return service.get()


@router.put(
    "/branding",
    response_model=BrandingRead,
    dependencies=[Depends(can_edit), Depends(has_branding)],
)
def update_branding(
    data: BrandingUpdate,
    service: BrandingService = Depends(get_branding_service),
) -> BrandingRead:
    return service.update(data)


@router.put(
    "/branding/dashboard",
    response_model=BrandingRead,
    dependencies=[Depends(can_edit), Depends(has_dashboard_layout)],
)
def update_dashboard_layout(
    layout: DashboardLayout,
    service: BrandingService = Depends(get_branding_service),
) -> BrandingRead:
    """Replace the dashboard widget composition (widgets, order, span, viz)."""
    return service.update_dashboard(layout)


@router.post(
    "/branding/dashboard/reset",
    response_model=BrandingRead,
    dependencies=[Depends(can_edit)],
)
def reset_dashboard_layout(
    service: BrandingService = Depends(get_branding_service),
) -> BrandingRead:
    return service.reset_dashboard()
