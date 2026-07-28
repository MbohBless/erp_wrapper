"""Budget lines (app DB): a yearly target per category, mapped to a SYSCOHADA
account group so it can be compared against actual ledger figures."""

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Budget(Base):
    __tablename__ = "budget_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fiscal_year: Mapped[str] = mapped_column(String(10), index=True)
    category: Mapped[str] = mapped_column(String(120))
    account_prefix: Mapped[str] = mapped_column(String(20))  # e.g. "70", "601", "66"
    amount: Mapped[float] = mapped_column(Float, default=0)   # yearly total (= sum of months)
    months_json: Mapped[str] = mapped_column(Text, default="[]")  # 12 monthly targets
