"""First-time books setup state (one row per tenant, app DB).

Tracks whether the business's opening balances have been posted to the ledger,
so the setup wizard runs once per tenant. Business data itself lives in ERPNext.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.mixins import TenantScoped


class BooksSetup(Base, TenantScoped):
    __tablename__ = "books_setup"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_books_setup_tenant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    setup_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    start_date: Mapped[str] = mapped_column(String(20), default="")
    opening_ref: Mapped[str] = mapped_column(String(140), default="")  # Journal Entry name
    payload_json: Mapped[str] = mapped_column(Text, default="")        # submitted figures (audit)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
