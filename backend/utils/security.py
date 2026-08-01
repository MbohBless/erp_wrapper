"""Security primitives: password hashing (bcrypt) and JWT tokens.

Infrastructure helpers only — no business rules. Used by the service layer.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str,
    role: str,
    tenant_id: str,
    expires_minutes: int | None = None,
) -> str:
    """Mint an access token bound to a user *and* the tenant they signed in to.

    The ``tid`` claim is not decoration: it is checked against the tenant the
    request resolved to, so a token minted on one workspace is inert on
    another even though both are signed with the same key.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "tid": tenant_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
