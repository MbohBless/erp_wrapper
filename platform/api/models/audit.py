"""Audit log for control-plane actions.

Suspending a customer, changing their plan or dropping their site are actions
someone will eventually have to answer for. Every mutating endpoint writes one
row here; the log is append-only by convention (there is no update or delete
path in the repository).
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

ACTION_TENANT_CREATED = "tenant.created"
ACTION_TENANT_UPDATED = "tenant.updated"
ACTION_TENANT_PROVISIONED = "tenant.provisioned"
ACTION_TENANT_SUSPENDED = "tenant.suspended"
ACTION_TENANT_RESUMED = "tenant.resumed"
ACTION_TENANT_ARCHIVED = "tenant.archived"
ACTION_TENANT_PURGED = "tenant.purged"
ACTION_PLAN_CHANGED = "tenant.plan_changed"
ACTION_DOMAIN_ADDED = "tenant.domain_added"
ACTION_DOMAIN_REMOVED = "tenant.domain_removed"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
