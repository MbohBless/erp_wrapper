"""App-DB access for inbound provider callbacks.

The unique (tenant, provider, event_key) constraint is the idempotency guard:
:meth:`claim` returns ``False`` for a delivery already seen, which is how a
retried callback becomes a no-op instead of a second credit.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.webhook_event import OUTCOME_ACCEPTED, WebhookEvent


class WebhookEventRepository:
    def __init__(self, db: Session, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def claim(self, provider: str, event_key: str, payload: str) -> WebhookEvent | None:
        """Record a delivery, or return ``None`` if it was already recorded.

        Relies on the database's unique constraint rather than a read-then-write
        check, so two callbacks arriving at once cannot both pass.
        """
        event = WebhookEvent(
            tenant_id=self.tenant_id,
            provider=provider,
            event_key=event_key,
            outcome=OUTCOME_ACCEPTED,
            payload=payload[:20000],
        )
        self.db.add(event)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return None
        self.db.refresh(event)
        return event

    def record_outcome(self, event: WebhookEvent, outcome: str, detail: str = "") -> None:
        event.outcome = outcome
        event.detail = detail[:255]
        self.db.commit()

    def get(self, provider: str, event_key: str) -> WebhookEvent | None:
        return self.db.scalar(
            select(WebhookEvent).where(
                WebhookEvent.tenant_id == self.tenant_id,
                WebhookEvent.provider == provider,
                WebhookEvent.event_key == event_key,
            )
        )

    def list(self, provider: str | None = None, limit: int = 100) -> list[WebhookEvent]:
        stmt = select(WebhookEvent).where(WebhookEvent.tenant_id == self.tenant_id)
        if provider:
            stmt = stmt.where(WebhookEvent.provider == provider)
        return list(
            self.db.scalars(stmt.order_by(WebhookEvent.id.desc()).limit(limit))
        )

    def delete_all(self) -> None:
        for row in self.db.scalars(
            select(WebhookEvent).where(WebhookEvent.tenant_id == self.tenant_id)
        ):
            self.db.delete(row)
        self.db.commit()
