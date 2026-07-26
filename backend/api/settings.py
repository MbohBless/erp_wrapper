"""Settings endpoints: company / branding profile used on report letterheads.

Access (Administrator always allowed):
  - read: any authenticated user (needed to render branding).
  - update: Manager, Accountant.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_current_user, require_roles
from database import get_db
from models.user import Role
from repositories.company_repository import CompanyRepository
from schemas.company import CompanyProfileRead, CompanyProfileUpdate
from services.company_service import CompanyService

router = APIRouter(prefix="/settings", tags=["settings"])

can_edit = require_roles(Role.MANAGER, Role.ACCOUNTANT)


def _service(db: Session = Depends(get_db)) -> CompanyService:
    return CompanyService(CompanyRepository(db))


@router.get(
    "/company-profile",
    response_model=CompanyProfileRead,
    dependencies=[Depends(get_current_user)],
)
def get_company_profile(service: CompanyService = Depends(_service)) -> CompanyProfileRead:
    return service.get_profile()


@router.put(
    "/company-profile",
    response_model=CompanyProfileRead,
    dependencies=[Depends(can_edit)],
)
def update_company_profile(
    data: CompanyProfileUpdate,
    service: CompanyService = Depends(_service),
) -> CompanyProfileRead:
    return service.update_profile(data)
