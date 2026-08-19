"""Audit log business logic.

Reading only. Events are written by the audit middleware; nothing here creates
one, and no route does either.
"""

from datetime import datetime

from repositories.audit_repository import AuditRepository
from schemas.audit import AuditEventRead


class AuditService:
    def __init__(self, repo: AuditRepository) -> None:
        self.repo = repo

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
    ) -> list[AuditEventRead]:
        # Cap the page size here rather than trusting the query string: this
        # table grows without bound, and one request should not be able to ask
        # for all of it.
        limit = max(1, min(limit, 500))
        events = self.repo.list(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            succeeded=succeeded,
            since=since,
            until=until,
            limit=limit,
            offset=max(0, offset),
        )
        return [AuditEventRead.model_validate(e) for e in events]
