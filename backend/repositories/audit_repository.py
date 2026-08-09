"""Audit event data-access. Append and read only — by design.

Tenant-scoped like every other app-owned table: constructed for one tenant, and
every query filters on it. Writes *stamp* the tenant from the repository rather
than trusting anything in the event.

There is deliberately no ``update`` and no ``delete``. Retention, when it is
needed, belongs in an explicit operator task that says what it is doing — not in
a method sitting next to the writer, one typo away from erasing the trail.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.audit import AuditEvent


class AuditRepository:
    def __init__(self, db: Session, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def record(self, **fields) -> AuditEvent:
        # tenant_id is stamped here and never read from the caller's payload.
        fields.pop("tenant_id", None)
        event = AuditEvent(tenant_id=self.tenant_id, **fields)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list(
        self,
        *,
        actor_id: int | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        succeeded: bool | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        stmt = select(AuditEvent).where(AuditEvent.tenant_id == self.tenant_id)
        if actor_id is not None:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        if resource_type:
            stmt = stmt.where(AuditEvent.resource_type == resource_type)
        if succeeded is not None:
            stmt = stmt.where(AuditEvent.succeeded == succeeded)
        if since is not None:
            stmt = stmt.where(AuditEvent.created_at >= since)
        if until is not None:
            stmt = stmt.where(AuditEvent.created_at <= until)
        stmt = stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        return list(self.db.scalars(stmt.limit(limit).offset(offset)))

    def count(self) -> int:
        from sqlalchemy import func as sa_func

        return int(
            self.db.scalar(
                select(sa_func.count(AuditEvent.id)).where(
                    AuditEvent.tenant_id == self.tenant_id
                )
            )
            or 0
        )
