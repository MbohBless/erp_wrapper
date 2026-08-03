"""Inbound provider callbacks, recorded before they are acted on.

Mobile-money providers retry callbacks and deliver them out of order — that is
normal operation, not an error. Writing every delivery here first, keyed on a
unique (tenant, provider, event_key), makes replay a no-op instead of a double
credit.

The row is also the audit trail for a disputed payment: it holds exactly what
the provider sent and when, which is the only evidence available months later.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.mixins import TenantScoped

OUTCOME_ACCEPTED = "accepted"        # verified and applied
OUTCOME_DUPLICATE = "duplicate"      # already seen; ignored
OUTCOME_UNKNOWN_INTENT = "unknown"   # no matching intent
OUTCOME_REJECTED = "rejected"        # failed verification
OUTCOME_ERROR = "error"              # handler raised


class WebhookEvent(Base, TenantScoped):
    __tablename__ = "webhook_event"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", "event_key", name="uq_webhook_event_key"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # Provider transaction reference, or a hash of the body when the provider
    # gives us nothing stable to key on.
    event_key: Mapped[str] = mapped_column(String(160), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default=OUTCOME_ACCEPTED)
    detail: Mapped[str] = mapped_column(String(255), default="")
    payload: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
