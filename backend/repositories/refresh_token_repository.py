"""Refresh token data-access. Tenant-scoped like every app-owned table."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def create(
        self,
        *,
        user_id: int,
        token_hash: str,
        family_id: str,
        expires_at: datetime,
        created_ip: str = "",
        user_agent: str = "",
    ) -> RefreshToken:
        token = RefreshToken(
            tenant_id=self.tenant_id,  # stamped, never taken from a payload
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
            created_ip=created_ip[:64],
            user_agent=user_agent[:255],
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.tenant_id == self.tenant_id,
            )
        )

    def revoke(self, token: RefreshToken, reason: str) -> None:
        token.revoked_at = datetime.now(timezone.utc)
        token.revoked_reason = reason[:40]
        self.db.commit()

    def revoke_family(self, family_id: str, reason: str) -> int:
        """Kill an entire rotation chain.

        Used when a token that was already rotated is presented again: one of
        the two holders is an attacker and there is no way to tell which, so
        both lose the session.
        """
        result = self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.tenant_id == self.tenant_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc), revoked_reason=reason[:40])
        )
        self.db.commit()
        return int(result.rowcount or 0)

    def revoke_all_for_user(self, user_id: int, reason: str) -> int:
        result = self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.tenant_id == self.tenant_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc), revoked_reason=reason[:40])
        )
        self.db.commit()
        return int(result.rowcount or 0)

    def purge_expired(self) -> int:
        """Housekeeping: expired rows carry no security value once past use."""
        from sqlalchemy import delete

        result = self.db.execute(
            delete(RefreshToken).where(
                RefreshToken.tenant_id == self.tenant_id,
                RefreshToken.expires_at < datetime.now(timezone.utc),
            )
        )
        self.db.commit()
        return int(result.rowcount or 0)
