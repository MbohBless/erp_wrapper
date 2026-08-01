"""Schemas for the control-plane -> tenant-app internal API."""

from typing import Annotated

from pydantic import BaseModel, EmailStr, Field


class TenantBootstrapIn(BaseModel):
    admin_email: EmailStr
    admin_password: Annotated[str, Field(min_length=8, max_length=128)]
    admin_name: Annotated[str, Field(max_length=255)] = "Administrator"
    company_name: Annotated[str, Field(max_length=200)] = ""
    app_name: Annotated[str, Field(max_length=80)] = ""


class TenantBootstrapOut(BaseModel):
    tenant_id: str
    admin_created: bool
    admin_email: EmailStr


class TenantPurgeOut(BaseModel):
    tenant_id: str
    users_deleted: int
