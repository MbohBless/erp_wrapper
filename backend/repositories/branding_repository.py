"""App-DB access for tenant branding (one row per tenant)."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.branding import TenantBranding


def _loads(raw: str, fallback: dict | None = None) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (ValueError, TypeError):
        return dict(fallback or {})
    return value if isinstance(value, dict) else dict(fallback or {})


class BrandingRepository:
    """Every query is bound to one tenant at construction time.

    The repository never exposes an unscoped read: there is no method that can
    return another tenant's branding even by accident.
    """

    def __init__(self, db: Session, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def get(self) -> TenantBranding:
        """Return this tenant's branding row, creating defaults if absent."""
        row = self.db.scalar(
            select(TenantBranding).where(TenantBranding.tenant_id == self.tenant_id)
        )
        if row is None:
            row = TenantBranding(tenant_id=self.tenant_id)
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def as_dict(self) -> dict:
        row = self.get()
        return {
            "app_name": row.app_name,
            "short_name": row.short_name,
            "tagline": row.tagline,
            "support_email": row.support_email,
            "support_url": row.support_url,
            "logo_light_data_url": row.logo_light_data_url,
            "logo_dark_data_url": row.logo_dark_data_url,
            "favicon_data_url": row.favicon_data_url,
            "light_tokens": _loads(row.light_tokens_json),
            "dark_tokens": _loads(row.dark_tokens_json),
            "font_heading": row.font_heading,
            "font_body": row.font_body,
            "default_theme": row.default_theme,
            "dashboard": _loads(row.dashboard_layout_json),
        }

    def update(self, data: dict) -> TenantBranding:
        row = self.get()
        scalar_fields = (
            "app_name",
            "short_name",
            "tagline",
            "support_email",
            "support_url",
            "logo_light_data_url",
            "logo_dark_data_url",
            "favicon_data_url",
            "font_heading",
            "font_body",
            "default_theme",
        )
        for field in scalar_fields:
            if field in data:
                setattr(row, field, data[field])
        if "light_tokens" in data:
            row.light_tokens_json = json.dumps(data["light_tokens"])
        if "dark_tokens" in data:
            row.dark_tokens_json = json.dumps(data["dark_tokens"])
        if "dashboard" in data:
            row.dashboard_layout_json = json.dumps(data["dashboard"])
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self) -> None:
        row = self.db.scalar(
            select(TenantBranding).where(TenantBranding.tenant_id == self.tenant_id)
        )
        if row is not None:
            self.db.delete(row)
            self.db.commit()
