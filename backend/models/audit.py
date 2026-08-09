"""Audit log: who did what, when, from where.

Append-only by construction. There is no update or delete anywhere in the
repository, and no route exposes one — a log an administrator can quietly edit
answers "what happened?" with "whatever the last person to touch it preferred".

What is recorded is deliberately narrow: actor, action, target, outcome, time,
address. Request bodies are **not** stored. They would carry passwords on
``/auth`` routes and customer data everywhere else, turning the audit trail into
a second, less guarded copy of the database.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.mixins import TenantScoped


class AuditEvent(Base, TenantScoped):
    __tablename__ = "audit_events"
    __table_args__ = (
        # The two questions actually asked of an audit log: "what happened
        # recently?" and "what has this person been doing?"
        Index("ix_audit_tenant_time", "tenant_id", "created_at"),
        Index("ix_audit_tenant_actor", "tenant_id", "actor_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Actor. The id may be null for an unauthenticated attempt (a failed login
    # still matters), so the email is stored alongside rather than joined —
    # deleting a user must not erase what they did.
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False, default="")

    # What happened. `action` is a stable verb ("user.create", "auth.login"),
    # derived from the route; `method` and `path` keep the raw request for when
    # the verb turns out not to be specific enough.
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    path: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    # The thing acted on, when the route identifies one.
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # A refused attempt is often the interesting one, so failures are recorded
    # exactly like successes rather than being filtered out.
    succeeded: Mapped[bool] = mapped_column(default=True, nullable=False)

    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Ties an entry to the matching application log lines.
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)

    # Server-side UTC. Never a client-supplied timestamp: the one thing an
    # attacker would most like to control is when the record says it happened.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
