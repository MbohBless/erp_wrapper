"""Refresh tokens: server-side, revocable, single-use.

Access tokens are JWTs and cannot be withdrawn once issued — the only lever is
their expiry. That is fine for a 60-minute credential and useless for a
long-lived one, so refresh tokens are stored here instead of being signed and
forgotten. The consequence that matters: a stolen session can actually be cut
off, which a pure-JWT design cannot do at all.

Three properties, each load-bearing:

**Hashed at rest.** Only a SHA-256 of the token is stored. Read access to this
table — a backup, a stray query, a report — must not hand out working sessions.

**Single use.** Every refresh rotates: the presented token is revoked and a new
one issued.

**Family-tracked.** Rotation means a token presented twice is either a bug or a
theft. `family_id` groups a chain back to one login, so seeing a
revoked token replayed lets the whole chain be killed rather than guessing
which copy was the attacker's.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.mixins import TenantScoped


class RefreshToken(Base, TenantScoped):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tenant_hash", "tenant_id", "token_hash"),
        Index("ix_refresh_family", "family_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # SHA-256 of the token. Never the token itself.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Shared by every token descended from one login.
    family_id: Mapped[str] = mapped_column(String(36), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Why it was revoked — "rotated", "logout", "reuse-detected". Worth keeping:
    # it is the difference between a normal sign-out and a stolen session.
    revoked_reason: Mapped[str] = mapped_column(String(40), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    @property
    def is_active(self) -> bool:
        from datetime import timezone as _tz

        if self.revoked_at is not None:
            return False
        expires = self.expires_at
        # SQLite hands back naive datetimes; compare in UTC either way.
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=_tz.utc)
        return expires > datetime.now(_tz.utc)
