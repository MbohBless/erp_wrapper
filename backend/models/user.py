"""User ORM model and Role enum (roles per docs/system-design.md §5)."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.mixins import TenantScoped


class Role(str, Enum):
    ADMINISTRATOR = "Administrator"
    MANAGER = "Manager"
    SALES = "Sales"
    STORE_KEEPER = "Store Keeper"
    ACCOUNTANT = "Accountant"
    BIOMEDICAL_ENGINEER = "Biomedical Engineer"


def assignable_roles() -> list[Role]:
    """The roles this deployment will hand out.

    Everything in `Role` minus whatever DISABLED_ROLES names. Administrator is
    never removable — a deployment that could disable it could lock itself out
    of its own user administration with no way back in.
    """
    from config import get_settings

    disabled = {r.strip().casefold() for r in get_settings().disabled_roles if r.strip()}
    return [
        r for r in Role
        if r is Role.ADMINISTRATOR or r.value.casefold() not in disabled
    ]


class User(Base, TenantScoped):
    __tablename__ = "users"
    # Email is unique *within* a tenant, not globally: two customers may each
    # have an admin@ account, and one must never collide with the other.
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # Stored as its string value (Role subclasses str), e.g. "Administrator".
    role: Mapped[str] = mapped_column(String(50), nullable=False, default=Role.SALES.value)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
