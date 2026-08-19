"""Audit log data access.

Append and read only — there is deliberately no update or delete method. If the
log can be edited from the application it is not evidence of anything.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.audit import AuditLog


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self, actor_email: str, action: str, tenant_id: str = "", detail: str = ""
    ) -> AuditLog:
        entry = AuditLog(
            actor_email=actor_email,
            action=action,
            tenant_id=tenant_id,
            detail=detail[:4000],
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list(
        self,
        tenant_id: str | None = None,
        action: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        stmt = select(AuditLog)
        if tenant_id:
            stmt = stmt.where(AuditLog.tenant_id == tenant_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        return list(self.db.scalars(stmt.offset(skip).limit(limit)))
