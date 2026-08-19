"""Plan data access."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.plan import Plan


def features_of(plan: Plan) -> list[str]:
    try:
        value = json.loads(plan.features_json or "[]")
    except (ValueError, TypeError):
        return []
    return [str(f) for f in value] if isinstance(value, list) else []


class PlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, code: str) -> Plan | None:
        return self.db.get(Plan, code)

    def list(self, include_inactive: bool = True) -> list[Plan]:
        stmt = select(Plan).order_by(Plan.price_xaf)
        if not include_inactive:
            stmt = stmt.where(Plan.is_active.is_(True))
        return list(self.db.scalars(stmt))

    def add(self, plan: Plan) -> Plan:
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def save(self, plan: Plan) -> Plan:
        self.db.commit()
        self.db.refresh(plan)
        return plan
