"""Authentication schemas (Pydantic V2)."""

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT claims."""

    sub: str | None = None  # user id
    role: str | None = None
    exp: int | None = None
