"""Encryption for tenant-held third-party credentials.

A tenant's mobile-money API keys let anyone holding them move that tenant's
money. They must not sit in the database as plaintext, so every credential is
sealed with Fernet before it is stored and only opened at the moment a request
is made.

The key comes from ``SECRET_ENCRYPTION_KEY``; when unset it is derived from
``JWT_SECRET_KEY`` so a development install works out of the box. Set the
dedicated variable in production — rotating the JWT secret would otherwise make
every stored credential unreadable.

Mirrors ``platform/api/utils/crypto.py`` deliberately rather than sharing code:
the two services have separate databases, separate keys and separate blast
radii, and a shared library would quietly couple them.
"""

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from config import settings

# Marks a value as ciphertext so a row written before encryption was switched
# on still reads back rather than raising.
_PREFIX = "enc:v1:"


class SecretUnreadable(RuntimeError):
    """Ciphertext could not be opened with the configured key."""


def _fernet() -> Fernet:
    raw = settings.secret_encryption_key or settings.jwt_secret_key
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    if not value:
        return ""
    return f"{_PREFIX}{_fernet().encrypt(value.encode('utf-8')).decode('ascii')}"


def decrypt(value: str) -> str:
    if not value:
        return ""
    if not value.startswith(_PREFIX):
        return value  # pre-encryption plaintext; re-saved on next write
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretUnreadable(
            "Stored credential could not be decrypted. SECRET_ENCRYPTION_KEY "
            "has probably changed since it was saved; re-enter the credential."
        ) from exc


def encrypt_json(data: dict[str, Any]) -> str:
    """Seal a whole credential set. Providers need differently-shaped secrets
    (username/password, apiuser/apikey, subscription key + api user + api key),
    so the column stores an encrypted JSON blob rather than fixed fields."""
    return encrypt(json.dumps(data, separators=(",", ":")))


def decrypt_json(value: str) -> dict[str, Any]:
    raw = decrypt(value)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def mask(value: str, keep: int = 4) -> str:
    """Render a secret for display: last few characters only, never the whole."""
    if not value:
        return ""
    if len(value) <= keep:
        return "•" * len(value)
    return "•" * (len(value) - keep) + value[-keep:]
