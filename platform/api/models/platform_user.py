"""Platform operators — the people who run the SaaS, not tenant users.

Kept in a separate table with a separate signing key from tenant users. A
tenant administrator is powerful inside one workspace; a platform operator can
suspend every workspace. The two must never be represented by the same record
or authenticated by the same token.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class PlatformRole(str, Enum):
    OWNER = "Owner"        # everything, including operator management
    OPERATOR = "Operator"  # provision, suspend, resume, edit tenants
    SUPPORT = "Support"    # read-only across the registry
    BILLING = "Billing"    # plans and read-only tenant view


class PlatformUser(Base):
    __tablename__ = "platform_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PlatformRole.SUPPORT.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
