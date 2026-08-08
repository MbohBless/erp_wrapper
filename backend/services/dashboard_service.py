"""Dashboard business logic, including per-role field visibility."""

from __future__ import annotations

from datetime import date

from models.user import Role
from repositories.dashboard_repository import DashboardRepository
from schemas.dashboard import DashboardSummary

# --- Per-role visibility policy -------------------------------------------
#
# The dashboard used to be role-agnostic while `/finance/*` was restricted to
# Manager + Accountant, so a Store Keeper denied the finance pages still read
# the company's revenue and receivables off their own dashboard. Same numbers,
# different door.
#
# Three tiers:
#
#   operational   stock levels and expiry — everyone doing the work needs these
#   commercial    revenue, trend, segment mix, top customer, recent activity
#   financial     receivables, payables, inventory valuation — the company's
#                 position, which is management and finance only
#
# Filtering happens HERE, not in the router and not in the UI: the response for
# a Store Keeper must not contain the withheld numbers at all. A hidden card in
# the frontend is cosmetic — the payload is what an inspector or a scripted
# client actually sees.
_OPERATIONAL = frozenset({"low_stock_count", "low_stock_items", "expiring_batches"})

_COMMERCIAL = frozenset(
    {
        "revenue_today",
        "revenue_trend",
        "revenue_by_segment",
        "top_customer",
        "recent_activity",
    }
)

_FINANCIAL = frozenset(
    {"outstanding_customers", "outstanding_suppliers", "inventory_value"}
)

VISIBLE_FIELDS: dict[str, frozenset[str]] = {
    Role.ADMINISTRATOR.value: _OPERATIONAL | _COMMERCIAL | _FINANCIAL,
    Role.MANAGER.value: _OPERATIONAL | _COMMERCIAL | _FINANCIAL,
    Role.ACCOUNTANT.value: _OPERATIONAL | _COMMERCIAL | _FINANCIAL,
    # Sales carry a quota, so they see commercial performance — but not the
    # company's supplier exposure or receivables position.
    Role.SALES.value: _OPERATIONAL | _COMMERCIAL,
    Role.STORE_KEEPER.value: _OPERATIONAL,
    Role.BIOMEDICAL_ENGINEER.value: _OPERATIONAL,
}

# Fields that are withheld by being emptied rather than nulled, because the UI
# iterates them. `low_stock_count` is never withheld from anyone.
_ALL_OPTIONAL = _COMMERCIAL | _FINANCIAL


class DashboardService:
    def __init__(self, repo: DashboardRepository) -> None:
        self.repo = repo

    async def get_summary(self, role: str | None = None) -> DashboardSummary:
        """Build the dashboard, filtered to what ``role`` may see.

        ``role=None`` returns everything. That is only for internal callers such
        as the PDF report builder, which has already run its own authorisation —
        never pass a request's role through as None.
        """
        summary = await self.repo.get_summary(date.today())
        if role is None:
            return summary
        return self.project(summary, role)

    @staticmethod
    def project(summary: DashboardSummary, role: str) -> DashboardSummary:
        """Blank every field ``role`` may not see.

        An unknown role gets the operational tier only. Failing closed matters
        here: a role added to the enum without a line in ``VISIBLE_FIELDS``
        should under-share, not hand out the ledger.
        """
        allowed = VISIBLE_FIELDS.get(role, _OPERATIONAL)
        withheld = {f: None for f in _ALL_OPTIONAL - allowed}
        return summary.model_copy(update=withheld) if withheld else summary
