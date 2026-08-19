"""Plan business logic."""

import json

from fastapi import HTTPException, status

from models.plan import Plan
from repositories.plan_repository import PlanRepository, features_of
from repositories.tenant_repository import TenantRepository
from schemas.plan import PlanCreate, PlanRead, PlanUpdate


class PlanService:
    def __init__(self, plans: PlanRepository, tenants: TenantRepository) -> None:
        self.plans = plans
        self.tenants = tenants

    def _read(self, plan: Plan) -> PlanRead:
        return PlanRead(
            code=plan.code,
            name=plan.name,
            description=plan.description,
            features=features_of(plan),
            max_users=plan.max_users,
            price_xaf=plan.price_xaf,
            is_active=plan.is_active,
            created_at=plan.created_at,
            tenant_count=self.tenants.count_for_plan(plan.code),
        )

    def list(self) -> list[PlanRead]:
        return [self._read(p) for p in self.plans.list()]

    def get(self, code: str) -> PlanRead:
        plan = self.plans.get(code)
        if plan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
        return self._read(plan)

    def create(self, data: PlanCreate) -> PlanRead:
        if self.plans.get(data.code) is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"Plan '{data.code}' already exists."
            )
        plan = Plan(
            code=data.code,
            name=data.name,
            description=data.description,
            features_json=json.dumps(data.features),
            max_users=data.max_users,
            price_xaf=data.price_xaf,
            is_active=data.is_active,
        )
        return self._read(self.plans.add(plan))

    def update(self, code: str, data: PlanUpdate) -> PlanRead:
        plan = self.plans.get(code)
        if plan is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")

        if data.is_active is False and self.tenants.count_for_plan(code) > 0:
            # Deactivating a plan that workspaces are on would silently strip
            # their features at the next resolve. Force the migration first.
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{self.tenants.count_for_plan(code)} workspace(s) are on this "
                "plan; move them before deactivating it.",
            )

        for field in ("name", "description", "max_users", "price_xaf", "is_active"):
            value = getattr(data, field)
            if value is not None:
                setattr(plan, field, value)
        if data.features is not None:
            plan.features_json = json.dumps(data.features)
        return self._read(self.plans.save(plan))
