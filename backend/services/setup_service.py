"""First-time setup business logic: read status, post opening balances once."""

from fastapi import HTTPException

from repositories.books_setup_repository import BooksSetupRepository
from repositories.budget_repository import BudgetRepository
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
    ) -> None:
        self.erp = erp
        self.store = store
        self.budgets = budgets

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
        opening_ref = await self.erp.post_opening(data)
        self.store.mark_complete(data.start_date, opening_ref, data.model_dump())
        # Carry the wizard's budget targets into the Budgets page.
        if data.budgets:
            fy = (data.start_date or "")[:4]
            self.budgets.replace_lines(
                fy, [(b.category, _guess_prefix(b.category), [b.yearly / 12] * 12) for b in data.budgets]
            )
        return self.status()
