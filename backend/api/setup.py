"""First-time setup endpoints: books-setup status + posting opening balances.

Access (Administrator always allowed):
  - status: any authenticated user.
  - post opening balances: Manager, Accountant.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_current_user, require_roles
from database import get_db
from integrations.erpnext import ERPNextClient, get_erpnext_client
from models.user import Role
from repositories.books_setup_repository import BooksSetupRepository
from repositories.budget_repository import BudgetRepository
from repositories.setup_repository import SetupRepository
from schemas.setup import OpeningBalancesInput, SetupStatus
from services.setup_service import SetupService

router = APIRouter(prefix="/setup", tags=["setup"])

can_post = require_roles(Role.MANAGER, Role.ACCOUNTANT)


def get_setup_service(
    client: ERPNextClient = Depends(get_erpnext_client),
    db: Session = Depends(get_db),
) -> SetupService:
    return SetupService(SetupRepository(client), BooksSetupRepository(db), BudgetRepository(db))


@router.get("/status", response_model=SetupStatus, dependencies=[Depends(get_current_user)])
def setup_status(service: SetupService = Depends(get_setup_service)) -> SetupStatus:
    return service.status()


@router.post("/opening-balances", response_model=SetupStatus, dependencies=[Depends(can_post)])
async def post_opening_balances(
    data: OpeningBalancesInput,
    service: SetupService = Depends(get_setup_service),
) -> SetupStatus:
    return await service.post_opening(data)
