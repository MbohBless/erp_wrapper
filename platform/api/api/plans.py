"""Plan endpoints.

Access: read for any operator; write for Owner and Billing.
"""

from fastapi import APIRouter, Depends, status

from api.deps import any_operator, can_bill, get_plan_service
from models.plan import KNOWN_FEATURES
from schemas.plan import PlanCreate, PlanRead, PlanUpdate
from services.plan_service import PlanService

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanRead], dependencies=[Depends(any_operator)])
def list_plans(service: PlanService = Depends(get_plan_service)) -> list[PlanRead]:
    return service.list()


@router.get("/features", dependencies=[Depends(any_operator)])
def list_features() -> dict:
    """The capability vocabulary shared with the tenant app's feature gates."""
    return {"features": list(KNOWN_FEATURES)}


@router.get("/{code}", response_model=PlanRead, dependencies=[Depends(any_operator)])
def get_plan(code: str, service: PlanService = Depends(get_plan_service)) -> PlanRead:
    return service.get(code)


@router.post(
    "",
    response_model=PlanRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_bill)],
)
def create_plan(
    data: PlanCreate, service: PlanService = Depends(get_plan_service)
) -> PlanRead:
    return service.create(data)


@router.patch("/{code}", response_model=PlanRead, dependencies=[Depends(can_bill)])
def update_plan(
    code: str, data: PlanUpdate, service: PlanService = Depends(get_plan_service)
) -> PlanRead:
    return service.update(code, data)
