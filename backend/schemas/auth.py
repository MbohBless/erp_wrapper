"""Authentication schemas (Pydantic V2)."""

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # Absent only in flows that do not mint one. Clients exchange it at
    # /auth/refresh when the access token expires.
    refresh_token: str | None = None
    expires_in: int | None = None  # seconds until the access token expires


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    """Decoded JWT claims."""

    sub: str | None = None  # user id
    role: str | None = None
    exp: int | None = None
