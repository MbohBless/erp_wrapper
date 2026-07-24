"""User request/response schemas (Pydantic V2)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models.user import Role

# bcrypt only considers the first 72 bytes of a password.
_PASSWORD = Field(min_length=8, max_length=72)


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: Role = Role.SALES
    is_active: bool = True


class UserCreate(UserBase):
    password: str = _PASSWORD


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
