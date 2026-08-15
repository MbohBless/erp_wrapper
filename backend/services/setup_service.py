"""First-time setup business logic: read status, post opening balances once."""

from fastapi import HTTPException

from repositories.books_setup_repository import BooksSetupRepository
from repositories.budget_repository import BudgetRepository
from repositories.reference_repository import ReferenceRepository
from repositories.setup_repository import SetupRepository
from schemas.setup import OpeningBalancesInput, SetupStatus


def _guess_prefix(category: str) -> str:
    """Best-guess SYSCOHADA account group for a free-text budget category."""
    c = category.lower()
    if any(k in c for k in ("revenue", "sales", "vente")):
        return "70"
    if any(k in c for k in ("purchase", "cogs", "achat", "goods")):
        return "601"
    if any(k in c for k in ("salar", "staff", "personnel", "wage", "payroll")):
        return "66"
    if any(k in c for k in ("rent", "util", "service", "loyer")):
        return "62"
    if "transport" in c:
        return "61"
    if any(k in c for k in ("tax", "impôt", "impot", "duty")):
        return "64"
    return "65"  # other expenses


class SetupService:
    def __init__(
        self,
        erp: SetupRepository,
        store: BooksSetupRepository,
        budgets: BudgetRepository,
        reference: ReferenceRepository | None = None,
    ) -> None:
        self.erp = erp
        self.store = store
        self.budgets = budgets
        # Used to explain a rejected start date before ERPNext refuses it.
        self.reference = reference

    async def _check_start_date(self, start_date: str) -> None:
        """Refuse a start date no fiscal year covers, in words that help.

        ERPNext's own refusal names a date the user did not type — the wizard
        derives posting dates from this one — and says nothing about creating a
        fiscal year, which is the fix.
        """
        if self.reference is None or not start_date:
            return
        years = await self.reference.active_fiscal_years()
        if not years:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No active fiscal year exists. Create one in ERPNext "
                    "(Accounting → Fiscal Year) covering "
                    f"{start_date}, then run setup again."
                ),
            )
        for y in years:
            if str(y.get("year_start_date")) <= start_date <= str(y.get("year_end_date")):
                return
        spans = ", ".join(
            f"{y.get('name')} ({y.get('year_start_date')} to {y.get('year_end_date')})"
            for y in years
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"The start date {start_date} is not inside any active fiscal "
                f"year. Available: {spans}. Either choose a date inside one, or "
                "create the fiscal year in ERPNext first."
            ),
        )

    def status(self) -> SetupStatus:
        row = self.store.get()
        return SetupStatus(
            setup_complete=row.setup_complete,
            start_date=row.start_date or "",
            opening_ref=row.opening_ref or "",
            posted_at=row.posted_at.isoformat() if row.posted_at else None,
        )

    async def post_opening(self, data: OpeningBalancesInput) -> SetupStatus:
        if self.store.get().setup_complete:
            raise HTTPException(status_code=409, detail="Your books are already set up.")
        await self._check_start_date(data.start_date)
        opening_ref = await self.erp.post_opening(data)
        self.store.mark_complete(data.start_date, opening_ref, data.model_dump())
        # Carry the wizard's budget targets into the Budgets page.
        if data.budgets:
            fy = (data.start_date or "")[:4]
            self.budgets.replace_lines(
                fy, [(b.category, _guess_prefix(b.category), [b.yearly / 12] * 12) for b in data.budgets]
            )
        return self.status()
