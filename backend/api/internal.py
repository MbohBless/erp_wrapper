"""Control-plane -> tenant-app callbacks.

Exempt from ``TenantMiddleware`` (see ``_EXEMPT_PREFIXES``) because these
endpoints act *on* a named tenant rather than being served *as* one: the
control plane provisions a workspace before any hostname routes to it.

Guarded by a shared secret, not a user session. If ``INTERNAL_API_TOKEN`` is
unset the whole router refuses every call — an unconfigured secret must fail
closed, never open. Do not expose this prefix through the public reverse proxy.
"""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.user import Role, User
from repositories.books_setup_repository import BooksSetupRepository
from repositories.branding_repository import BrandingRepository
from repositories.budget_repository import BudgetRepository
from repositories.company_repository import CompanyRepository
from repositories.user_repository import UserRepository
from schemas.internal import TenantBootstrapIn, TenantBootstrapOut, TenantPurgeOut
from utils.security import hash_password

router = APIRouter(prefix="/internal", tags=["internal"])


def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    expected = settings.internal_api_token
    if not expected:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Internal API is disabled (INTERNAL_API_TOKEN is not configured).",
        )
    # Constant-time compare: this secret is long-lived and network-reachable.
    if not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal token")


@router.post(
    "/tenants/{tenant_id}/bootstrap",
    response_model=TenantBootstrapOut,
    dependencies=[Depends(require_internal_token)],
)
def bootstrap_tenant(
    tenant_id: str,
    data: TenantBootstrapIn,
    db: Session = Depends(get_db),
) -> TenantBootstrapOut:
    """Create a new workspace's app-DB rows: admin user, profile, branding.

    Idempotent — the control plane retries provisioning, so a second call must
    not create a second administrator or reset a live workspace's branding.
    """
    users = UserRepository(db, tenant_id)
    created = False
    admin = users.get_by_email(data.admin_email)
    if admin is None:
        users.add(
            User(
                email=data.admin_email,
                full_name=data.admin_name,
                role=Role.ADMINISTRATOR.value,
                is_active=True,
                hashed_password=hash_password(data.admin_password),
            )
        )
        created = True

    profile = CompanyRepository(db, tenant_id)
    profile.get()
    if data.company_name:
        profile.update({"display_name": data.company_name, "legal_name": data.company_name})

    branding = BrandingRepository(db, tenant_id)
    branding.get()
    if data.app_name:
        branding.update({"app_name": data.app_name, "short_name": data.app_name[:24]})

    return TenantBootstrapOut(
        tenant_id=tenant_id,
        admin_created=created,
        admin_email=data.admin_email,
    )


@router.delete(
    "/tenants/{tenant_id}",
    response_model=TenantPurgeOut,
    dependencies=[Depends(require_internal_token)],
)
def purge_tenant(tenant_id: str, db: Session = Depends(get_db)) -> TenantPurgeOut:
    """Erase a workspace's app-DB footprint (offboarding).

    Only touches app-owned tables. ERPNext data is deleted separately by the
    control plane's provisioner, because dropping a site is not reversible and
    is sequenced after the customer's final data export.
    """
    users_deleted = UserRepository(db, tenant_id).delete_all()
    BudgetRepository(db, tenant_id).delete_all()
    BooksSetupRepository(db, tenant_id).delete()
    CompanyRepository(db, tenant_id).delete()
    BrandingRepository(db, tenant_id).delete()
    return TenantPurgeOut(tenant_id=tenant_id, users_deleted=users_deleted)
