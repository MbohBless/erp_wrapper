"""Plan schemas."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.plan import KNOWN_FEATURES


def _validate_features(value: list[str]) -> list[str]:
    unknown = sorted(set(value) - set(KNOWN_FEATURES))
    if unknown:
        raise ValueError(
            f"Unknown feature(s): {', '.join(unknown)}. "
            f"Known: {', '.join(KNOWN_FEATURES)}"
        )
    # Deduplicate but keep a stable order for display.
    seen: list[str] = []
    for f in value:
        if f not in seen:
            seen.append(f)
    return seen


class PlanBase(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=120)]
    description: str = ""
    features: list[str] = []
    max_users: Annotated[int, Field(ge=1, le=10000)] = 10
    price_xaf: Annotated[int, Field(ge=0)] = 0
    is_active: bool = True

    @field_validator("features")
    @classmethod
    def _features(cls, v: list[str]) -> list[str]:
        return _validate_features(v)


class PlanCreate(PlanBase):
    code: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{1,38}$")]


class PlanUpdate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    description: str | None = None
    features: list[str] | None = None
    max_users: Annotated[int, Field(ge=1, le=10000)] | None = None
    price_xaf: Annotated[int, Field(ge=0)] | None = None
    is_active: bool | None = None

    @field_validator("features")
    @classmethod
    def _features(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _validate_features(v)


class PlanRead(PlanBase):
    model_config = ConfigDict(from_attributes=True)

    code: str
    created_at: datetime
    tenant_count: int = 0
