"""Envelope encryption for tenant secrets at rest.

The registry stores every tenant's ERPNext API secret. A leaked control-plane
database would otherwise be a leak of every customer's ERP — so those columns
are encrypted with a key that lives in the environment, not in the database.

The key is derived (SHA-256) from ``SECRET_ENCRYPTION_KEY`` when set, and from
``JWT_SECRET_KEY`` otherwise, so a development install works out of the box.
Production should set the dedicated variable: rotating the JWT secret would
otherwise make every stored credential unreadable.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from config import settings

# Marks a value as ciphertext, so a database written before encryption was
# switched on still reads back correctly instead of raising.
_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    raw = settings.secret_encryption_key or settings.jwt_secret_key
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    if not value:
        return ""
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt(value: str) -> str:
    if not value:
        return ""
    if not value.startswith(_PREFIX):
        # Pre-encryption plaintext; return as-is so reads keep working while
        # the value is re-saved through the normal update path.
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken:
        # Wrong key: surface as "no credential" rather than a 500, so one bad
        # tenant row cannot take down resolution for everyone else.
        return ""
