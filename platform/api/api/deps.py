"""Control-plane dependencies: DB session, DI wiring, auth and RBAC."""

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

import secrets

from config import settings
from database import get_db
from integrations.tenant_app import TenantAppClient
from models.platform_user import PlatformRole, PlatformUser
from repositories.audit_repository import AuditRepository
from repositories.plan_repository import PlanRepository
from repositories.platform_user_repository import PlatformUserRepository
from repositories.tenant_repository import TenantRepository
from services.auth_service import PlatformAuthService, PlatformUserService
from services.plan_service import PlanService
from services.provisioning import Provisioner, build_provisioner
from services.tenant_service import TenantService
from utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# One provisioner per process: FrappeBenchProvisioner is stateless but the
# noop one accumulates a call log that tests read back.
_provisioner: Provisioner = build_provisioner()


def get_provisioner() -> Provisioner:
    return _provisioner


def get_tenant_app_client() -> TenantAppClient:
    return TenantAppClient()


# --- Repositories ---------------------------------------------------------
def get_tenant_repository(db: Session = Depends(get_db)) -> TenantRepository:
    return TenantRepository(db)


def get_plan_repository(db: Session = Depends(get_db)) -> PlanRepository:
    return PlanRepository(db)


def get_audit_repository(db: Session = Depends(get_db)) -> AuditRepository:
    return AuditRepository(db)


def get_platform_user_repository(
    db: Session = Depends(get_db),
) -> PlatformUserRepository:
    return PlatformUserRepository(db)


# --- Auth -----------------------------------------------------------------
def get_auth_service(
    repo: PlatformUserRepository = Depends(get_platform_user_repository),
) -> PlatformAuthService:
    return PlatformAuthService(repo)


def get_platform_user_service(
    repo: PlatformUserRepository = Depends(get_platform_user_repository),
) -> PlatformUserService:
    return PlatformUserService(repo)


def get_current_operator(
    token: str = Depends(oauth2_scheme),
    repo: PlatformUserRepository = Depends(get_platform_user_repository),
) -> PlatformUser:
    credentials_exc = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exc
    except InvalidTokenError:
        raise credentials_exc

    user = repo.get(int(subject))
    if user is None:
        raise credentials_exc
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    return user


def require_platform_roles(*roles: PlatformRole):
    """RBAC for operators. Unlike the tenant app, Owner is not implicitly
    allowed everywhere by accident — it is listed wherever it applies, so the
    matrix in docs/multi-tenancy.md can be read straight off the routers."""
    allowed = {r.value for r in roles}

    def checker(operator: PlatformUser = Depends(get_current_operator)) -> PlatformUser:
        if str(operator.role) in allowed:
            return operator
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    return checker


# Common role bundles.
any_operator = require_platform_roles(
    PlatformRole.OWNER, PlatformRole.OPERATOR, PlatformRole.SUPPORT, PlatformRole.BILLING
)
can_operate = require_platform_roles(PlatformRole.OWNER, PlatformRole.OPERATOR)
can_bill = require_platform_roles(PlatformRole.OWNER, PlatformRole.BILLING)
owner_only = require_platform_roles(PlatformRole.OWNER)


# --- Services -------------------------------------------------------------
def get_tenant_service(
    tenants: TenantRepository = Depends(get_tenant_repository),
    plans: PlanRepository = Depends(get_plan_repository),
    audit: AuditRepository = Depends(get_audit_repository),
    provisioner: Provisioner = Depends(get_provisioner),
    tenant_app: TenantAppClient = Depends(get_tenant_app_client),
    operator: PlatformUser = Depends(get_current_operator),
) -> TenantService:
    return TenantService(
        tenants, plans, audit, provisioner, tenant_app, actor_email=operator.email
    )


def get_plan_service(
    plans: PlanRepository = Depends(get_plan_repository),
    tenants: TenantRepository = Depends(get_tenant_repository),
) -> PlanService:
    return PlanService(plans, tenants)


def get_internal_tenant_service(
    tenants: TenantRepository = Depends(get_tenant_repository),
    plans: PlanRepository = Depends(get_plan_repository),
    audit: AuditRepository = Depends(get_audit_repository),
    provisioner: Provisioner = Depends(get_provisioner),
    tenant_app: TenantAppClient = Depends(get_tenant_app_client),
) -> TenantService:
    """Service for machine callers — no operator, so no audit attribution."""
    return TenantService(tenants, plans, audit, provisioner, tenant_app, actor_email="system")


# --- Internal (machine-to-machine) ----------------------------------------
def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    expected = settings.internal_api_token
    if not expected:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Internal API is disabled (INTERNAL_API_TOKEN is not configured).",
        )
    if not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal token")
