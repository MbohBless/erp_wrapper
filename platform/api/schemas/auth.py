"""Platform operator auth schemas."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models.platform_user import PlatformRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PlatformUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: PlatformRole
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


class PlatformUserCreate(BaseModel):
    email: EmailStr
    full_name: Annotated[str, Field(min_length=2, max_length=200)]
    password: Annotated[str, Field(min_length=12, max_length=128)]
    role: PlatformRole = PlatformRole.SUPPORT
    is_active: bool = True


class PlatformUserUpdate(BaseModel):
    full_name: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    password: Annotated[str, Field(min_length=12, max_length=128)] | None = None
    role: PlatformRole | None = None
    is_active: bool | None = None
