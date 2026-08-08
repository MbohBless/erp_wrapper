"""Shared FastAPI dependencies: DB session, DI providers, auth & RBAC."""

from collections.abc import Callable
from typing import TypeVar

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from database import get_db
from integrations.erpnext import ERPNextClient, get_erpnext_client
from models.user import Role, User
from repositories.batch_repository import BatchRepository
from repositories.branding_repository import BrandingRepository
from repositories.company_repository import CompanyRepository
from repositories.customer_repository import CustomerRepository
from repositories.dashboard_repository import DashboardRepository
from repositories.equipment_repository import EquipmentRepository
from repositories.finance_repository import FinanceRepository
from repositories.maintenance_repository import MaintenanceRepository
from repositories.payment_repository import PaymentRepository
from repositories.product_repository import ProductRepository
from repositories.purchase_repository import PurchaseRepository
from repositories.sales_repository import SalesRepository
from repositories.stock_entry_repository import StockEntryRepository
from repositories.stock_repository import StockRepository
from repositories.supplier_repository import SupplierRepository
from repositories.user_repository import UserRepository
from repositories.warehouse_repository import WarehouseRepository
from services.auth_service import AuthService
from services.branding_service import BrandingService
from services.company_service import CompanyService
from services.customer_service import CustomerService
from services.dashboard_service import DashboardService
from services.equipment_service import EquipmentService
from services.finance_service import FinanceService
from services.inventory_service import InventoryService
from services.maintenance_service import MaintenanceService
from services.payment_service import PaymentService
from services.product_service import ProductService
from services.purchase_service import PurchaseService
from services.report_service import ReportService
from services.sales_service import SalesService
from services.supplier_service import SupplierService
from services.user_service import UserService
from tenancy import TenantContext, current_tenant
from utils.security import decode_access_token

# tokenUrl is relative to the app root; drives Swagger's "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# --- Tenant ---------------------------------------------------------------
# Resolved by TenantMiddleware before any route runs. Exposed as dependencies
# so routers and services declare the tenant they need instead of reaching for
# the ContextVar themselves.
def get_tenant() -> TenantContext:
    return current_tenant()


def get_tenant_id(tenant: TenantContext = Depends(get_tenant)) -> str:
    return tenant.id


def require_feature(name: str):
    """Dependency factory gating a route on the tenant's plan features."""

    def checker(tenant: TenantContext = Depends(get_tenant)) -> TenantContext:
        if not tenant.has_feature(name):
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                f"'{name}' is not included in the {tenant.plan} plan.",
            )
        return tenant

    return checker


# --- DB-backed providers (users/auth): two-layer DI so the repository can be
#     injected/overridden independently of the service. Every app-DB repository
#     is constructed against the request's tenant. ---
def get_user_repository(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> UserRepository:
    return UserRepository(db, tenant_id)


def get_company_repository(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> CompanyRepository:
    return CompanyRepository(db, tenant_id)


def get_branding_repository(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> BrandingRepository:
    return BrandingRepository(db, tenant_id)


def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(repo)


def get_auth_service(
    repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(repo)


def get_company_service(
    repo: CompanyRepository = Depends(get_company_repository),
) -> CompanyService:
    return CompanyService(repo)


def get_branding_service(
    repo: BrandingRepository = Depends(get_branding_repository),
) -> BrandingService:
    return BrandingService(repo)


# --- ERPNext-backed service providers ---
# Every one wires ``Service(Repository(client))`` off the shared ERPNext client;
# the factory keeps that a single typed line instead of repeated boilerplate.
_ServiceT = TypeVar("_ServiceT")


def erpnext_service(
    build: Callable[[ERPNextClient], _ServiceT],
) -> Callable[..., _ServiceT]:
    def provider(
        client: ERPNextClient = Depends(get_erpnext_client),
    ) -> _ServiceT:
        return build(client)

    return provider


get_customer_service = erpnext_service(lambda c: CustomerService(CustomerRepository(c)))
get_supplier_service = erpnext_service(lambda c: SupplierService(SupplierRepository(c)))
get_product_service = erpnext_service(lambda c: ProductService(ProductRepository(c)))
get_sales_service = erpnext_service(lambda c: SalesService(SalesRepository(c)))
get_purchase_service = erpnext_service(lambda c: PurchaseService(PurchaseRepository(c)))
get_equipment_service = erpnext_service(
    lambda c: EquipmentService(EquipmentRepository(c))
)
get_maintenance_service = erpnext_service(
    lambda c: MaintenanceService(MaintenanceRepository(c))
)
get_finance_service = erpnext_service(lambda c: FinanceService(FinanceRepository(c)))
get_payment_service = erpnext_service(lambda c: PaymentService(PaymentRepository(c)))
get_dashboard_service = erpnext_service(
    lambda c: DashboardService(DashboardRepository(c))
)
def _build_inventory_service(client: ERPNextClient) -> InventoryService:
    return InventoryService(
        warehouses=WarehouseRepository(client),
        batches=BatchRepository(client),
        stock=StockRepository(client),
        stock_entries=StockEntryRepository(client),
        products=ProductRepository(client),
    )


# One builder, used by both the route dependency and the report service. These
# were two separate constructions of the same object; adding a repository to one
# and not the other is exactly how that drifted.
get_inventory_service = erpnext_service(_build_inventory_service)


def get_report_service(
    client: ERPNextClient = Depends(get_erpnext_client),
    company: CompanyService = Depends(get_company_service),
) -> ReportService:
    profile = company.get_profile().model_dump()
    return ReportService(
        finance=FinanceService(FinanceRepository(client)),
        inventory=_build_inventory_service(client),
        profile=profile,
        dashboard=DashboardService(DashboardRepository(client)),
    )


# --- Authentication ---
def get_current_user(
    token: str = Depends(oauth2_scheme),
    repo: UserRepository = Depends(get_user_repository),
    tenant: TenantContext = Depends(get_tenant),
) -> User:
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

    # Cross-tenant replay guard. All workspaces share one signing key, so a
    # token from tenant A is cryptographically valid on tenant B's host — this
    # claim check is what actually stops it. The repository lookup below is
    # tenant-scoped too, so this is defence in depth, not the only barrier.
    if payload.get("tid") != tenant.id:
        raise credentials_exc

    user = repo.get(int(subject))
    if user is None:
        raise credentials_exc
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
    return user


# --- Role-based access control ---
def require_roles(*roles: Role):
    """Dependency factory. Administrators are always allowed."""
    allowed = {r.value for r in roles}

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if (
            str(current_user.role) == Role.ADMINISTRATOR.value
            or str(current_user.role) in allowed
        ):
            return current_user
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    return checker
