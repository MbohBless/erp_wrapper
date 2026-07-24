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
from repositories.customer_repository import CustomerRepository
from repositories.dashboard_repository import DashboardRepository
from repositories.equipment_repository import EquipmentRepository
from repositories.finance_repository import FinanceRepository
from repositories.maintenance_repository import MaintenanceRepository
from repositories.product_repository import ProductRepository
from repositories.purchase_repository import PurchaseRepository
from repositories.sales_repository import SalesRepository
from repositories.stock_entry_repository import StockEntryRepository
from repositories.stock_repository import StockRepository
from repositories.supplier_repository import SupplierRepository
from repositories.user_repository import UserRepository
from repositories.warehouse_repository import WarehouseRepository
from services.auth_service import AuthService
from services.customer_service import CustomerService
from services.dashboard_service import DashboardService
from services.equipment_service import EquipmentService
from services.finance_service import FinanceService
from services.inventory_service import InventoryService
from services.maintenance_service import MaintenanceService
from services.product_service import ProductService
from services.purchase_service import PurchaseService
from services.sales_service import SalesService
from services.supplier_service import SupplierService
from services.user_service import UserService
from utils.security import decode_access_token

# tokenUrl is relative to the app root; drives Swagger's "Authorize" button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# --- DB-backed providers (users/auth): two-layer DI so the repository can be
#     injected/overridden independently of the service. ---
def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(repo)


def get_auth_service(
    repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(repo)


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
get_dashboard_service = erpnext_service(
    lambda c: DashboardService(DashboardRepository(c))
)
get_inventory_service = erpnext_service(
    lambda c: InventoryService(
        warehouses=WarehouseRepository(c),
        batches=BatchRepository(c),
        stock=StockRepository(c),
        stock_entries=StockEntryRepository(c),
    )
)


# --- Authentication ---
def get_current_user(
    token: str = Depends(oauth2_scheme),
    repo: UserRepository = Depends(get_user_repository),
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
