"""Unit tests for password hashing and JWT helpers."""

import jwt

from config import settings
from utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token(subject="42", role="Administrator", tenant_id="acme")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "Administrator"
    assert payload["tid"] == "acme"


def test_invalid_token_rejected():
    bad = create_access_token(subject="1", role="Sales", tenant_id="acme") + "tampered"
    try:
        decode_access_token(bad)
        assert False, "expected an invalid-token error"
    except jwt.InvalidTokenError:
        pass


def test_token_signed_with_configured_secret():
    token = create_access_token(subject="1", role="Sales", tenant_id="acme")
    # Decoding with the configured secret works...
    assert decode_access_token(token)["sub"] == "1"
    # ...and a different secret fails.
    try:
        jwt.decode(token, "other-secret", algorithms=[settings.jwt_algorithm])
        assert False, "expected signature verification failure"
    except jwt.InvalidTokenError:
        pass
