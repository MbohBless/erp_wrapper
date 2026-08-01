"""Tenant registry schemas."""

import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models.tenant import TENANT_STATUSES

_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")

# Subdomains we keep for ourselves. A tenant called "api" would sit on
# api.equimed.app and shadow platform infrastructure.
RESERVED_SLUGS = frozenset(
    {
        "www", "api", "app", "admin", "platform", "erp", "mail", "smtp",
        "status", "billing", "support", "docs", "static", "assets", "cdn",
        "internal", "control", "console", "dashboard", "equimed", "default",
    }
)


def _validate_slug(value: str) -> str:
    value = value.strip().lower()
    if not _SLUG.match(value):
        raise ValueError(
            "Workspace id must be 3-40 characters: lowercase letters, digits "
            "and hyphens, not starting or ending with a hyphen."
        )
    if value in RESERVED_SLUGS:
        raise ValueError(f"'{value}' is reserved and cannot be used as a workspace id.")
    return value


def _validate_host(value: str) -> str:
    value = value.strip().lower().rstrip(".")
    if not value or len(value) > 253:
        raise ValueError("Domain must be between 1 and 253 characters.")
    label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if not re.match(rf"^{label}(?:\.{label})+$", value):
        raise ValueError(f"'{value}' is not a valid domain name.")
    return value


class TenantDomainRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    host: str
    is_primary: bool
    verified_at: datetime | None = None


class TenantDomainCreate(BaseModel):
    host: str
    is_primary: bool = False

    @field_validator("host")
    @classmethod
    def _host(cls, v: str) -> str:
        return _validate_host(v)


class TenantCreate(BaseModel):
    id: Annotated[str, Field(description="Workspace slug — also the subdomain")]
    name: Annotated[str, Field(min_length=2, max_length=200)]
    plan_code: str
    contact_name: Annotated[str, Field(max_length=200)] = ""
    contact_email: EmailStr | None = None
    country: Annotated[str, Field(max_length=120)] = "Cameroon"
    notes: str = ""

    # ERPNext coordinates. Left blank, the service derives them from the
    # platform defaults (shared bench, site "<slug>.<suffix>").
    erpnext_url: str = ""
    erpnext_site: str = ""
    erpnext_api_key: str = ""
    erpnext_api_secret: str = ""

    # First administrator for the workspace, created via the tenant app's
    # internal bootstrap endpoint during provisioning.
    admin_email: EmailStr
    admin_password: Annotated[str, Field(min_length=8, max_length=128)]
    admin_name: Annotated[str, Field(max_length=200)] = "Administrator"

    @field_validator("id")
    @classmethod
    def _slug(cls, v: str) -> str:
        return _validate_slug(v)


class TenantUpdate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=200)] | None = None
    plan_code: str | None = None
    contact_name: Annotated[str, Field(max_length=200)] | None = None
    contact_email: EmailStr | None = None
    country: Annotated[str, Field(max_length=120)] | None = None
    notes: str | None = None
    erpnext_url: str | None = None
    erpnext_site: str | None = None
    erpnext_api_key: str | None = None
    erpnext_api_secret: str | None = None


class TenantRead(BaseModel):
    """Admin-facing view. Note there is no ERPNext *secret* field: the control
    plane can set one but never reads one back out over the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    plan_code: str
    contact_name: str
    contact_email: str
    country: str
    notes: str
    erpnext_url: str
    erpnext_site: str
    erpnext_api_key: str
    has_erpnext_secret: bool = False
    suspended_reason: str
    suspended_at: datetime | None
    provisioned_at: datetime | None
    created_at: datetime
    updated_at: datetime
    domains: list[TenantDomainRead] = []
    primary_host: str = ""


class TenantSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    plan_code: str
    primary_host: str = ""
    contact_email: str = ""
    created_at: datetime


class SuspendIn(BaseModel):
    reason: Annotated[str, Field(max_length=255)] = "Suspended by platform operator"


class StatusFilter(BaseModel):
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _known(cls, v: str | None) -> str | None:
        if v is not None and v not in TENANT_STATUSES:
            raise ValueError(f"status must be one of {', '.join(TENANT_STATUSES)}")
        return v


class ResolvedTenant(BaseModel):
    """The payload the tenant app consumes on every cold request.

    This is the only place ERPNext credentials leave the control plane, and it
    is served on the internal network behind a shared secret.
    """

    id: str
    name: str
    status: str
    plan: str
    erpnext_url: str
    erpnext_site: str | None = None
    erpnext_api_key: str
    erpnext_api_secret: str
    features: list[str]


class ProvisionResult(BaseModel):
    tenant: TenantRead
    provisioned: bool
    bootstrapped: bool
    messages: list[str] = []
