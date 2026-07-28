"""App-DB access for budget lines (monthly targets)."""

import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models.budget import Budget


def _months(row: Budget) -> list[float]:
    try:
        m = json.loads(row.months_json or "[]")
    except (ValueError, TypeError):
        m = []
    if not m:  # backward compat: spread a legacy yearly amount evenly
        m = [(row.amount or 0) / 12] * 12
    return [float(x) for x in (m + [0.0] * 12)[:12]]


class BudgetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_lines(self, fiscal_year: str) -> list[tuple[str, str, list[float]]]:
        rows = self.db.execute(
            select(Budget).where(Budget.fiscal_year == fiscal_year).order_by(Budget.id)
        ).scalars()
        return [(r.category, r.account_prefix, _months(r)) for r in rows]

    def replace_lines(self, fiscal_year: str, lines: list[tuple[str, str, list[float]]]) -> None:
        self.db.execute(delete(Budget).where(Budget.fiscal_year == fiscal_year))
        for category, prefix, months in lines:
            months = [float(x) for x in (months + [0.0] * 12)[:12]]
            self.db.add(Budget(
                fiscal_year=fiscal_year, category=category, account_prefix=prefix,
                amount=round(sum(months), 2), months_json=json.dumps(months),
            ))
        self.db.commit()
