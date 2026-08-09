"""Authentication business logic: sign-in, token refresh, sign-out."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from config import settings
from models.user import User
from repositories.refresh_token_repository import RefreshTokenRepository
from repositories.user_repository import UserRepository
from utils.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)

log = logging.getLogger("equimed.auth")

# Deliberately identical for "no such user" and "wrong password": distinguishing
# them turns the login form into a way to enumerate who has an account.
_BAD_CREDENTIALS = "Incorrect email or password"


class AuthService:
    def __init__(
        self,
        repo: UserRepository,
        refresh_repo: RefreshTokenRepository | None = None,
    ) -> None:
        self.repo = repo
        self.refresh_repo = refresh_repo

    # --- sign in ----------------------------------------------------------
    def authenticate(self, email: str, password: str) -> User:
        user = self.repo.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                _BAD_CREDENTIALS,
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive user")
        return user

    def _access_token(self, user: User) -> str:
        return create_access_token(
            subject=str(user.id),
            role=str(user.role),
            tenant_id=self.repo.tenant_id,
        )

    def _issue_refresh(
        self, user: User, family_id: str, ip: str = "", user_agent: str = ""
    ) -> str:
        assert self.refresh_repo is not None
        raw = new_refresh_token()
        self.refresh_repo.create(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            family_id=family_id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_expire_days),
            created_ip=ip,
            user_agent=user_agent,
        )
        # The caller gets the only copy of the raw value; we keep the hash.
        return raw

    def login(
        self, email: str, password: str, *, ip: str = "", user_agent: str = ""
    ) -> tuple[str, str | None, int]:
        """Authenticate and mint an access token, plus a refresh token.

        Returns ``(access_token, refresh_token, expires_in_seconds)``.
        """
        user = self.authenticate(email, password)
        access = self._access_token(user)
        refresh = None
        if self.refresh_repo is not None:
            # A new login starts a new family; existing sessions on other
            # devices are left alone.
            refresh = self._issue_refresh(user, str(uuid.uuid4()), ip, user_agent)
        return access, refresh, settings.access_token_expire_minutes * 60

    # --- refresh ----------------------------------------------------------
    def refresh(
        self, raw_token: str, *, ip: str = "", user_agent: str = ""
    ) -> tuple[str, str, int]:
        """Exchange a refresh token for a new pair, rotating the old one.

        Rotation is what makes theft detectable: each token works once, so a
        second presentation means two parties hold the same credential. When
        that happens the whole family is revoked — we cannot tell the legitimate
        user from the attacker, and logging both out is the safe answer.
        """
        if self.refresh_repo is None:
            raise HTTPException(
                status.HTTP_501_NOT_IMPLEMENTED, "Refresh is not configured"
            )

        invalid = HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

        stored = self.refresh_repo.get_by_hash(hash_refresh_token(raw_token))
        if stored is None:
            raise invalid

        if stored.revoked_at is not None:
            # Already used or explicitly revoked, and presented again.
            killed = self.refresh_repo.revoke_family(
                stored.family_id, "reuse-detected"
            )
            log.warning(
                "refresh token reuse detected; revoked %d token(s)",
                killed,
                extra={"user_id": stored.user_id, "family": stored.family_id},
            )
            raise invalid

        if not stored.is_active:  # expired
            raise invalid

        user = self.repo.get(stored.user_id)
        if user is None or not user.is_active:
            raise invalid

        self.refresh_repo.revoke(stored, "rotated")
        new_raw = self._issue_refresh(user, stored.family_id, ip, user_agent)
        return (
            self._access_token(user),
            new_raw,
            settings.access_token_expire_minutes * 60,
        )

    # --- sign out ---------------------------------------------------------
    def logout(self, raw_token: str | None, user: User | None = None) -> None:
        """Revoke the presented refresh token, or every session for the user.

        Without this, signing out only discarded the access token on the client
        while the refresh token stayed valid for weeks — a sign-out that does
        not end the session.
        """
        if self.refresh_repo is None:
            return
        if raw_token:
            stored = self.refresh_repo.get_by_hash(hash_refresh_token(raw_token))
            if stored is not None and stored.revoked_at is None:
                self.refresh_repo.revoke(stored, "logout")
                return
        if user is not None:
            self.refresh_repo.revoke_all_for_user(user.id, "logout")
