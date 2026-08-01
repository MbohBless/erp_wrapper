"""Tenant branding — the *application skin*.

One row per tenant. Owns everything a white-label customer can restyle without
touching code: product name, logos, the design-token overrides applied to
``app/globals.css``, and the dashboard widget layout.

Values are stored as JSON blobs but are never trusted on the way in or out:
``schemas.branding`` validates every token name against an allowlist and every
value against a strict pattern, because these end up inside a ``<style>`` tag.
See ``docs/multi-tenancy.md`` for the threat model.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.mixins import TenantScoped


class TenantBranding(Base, TenantScoped):
    __tablename__ = "tenant_branding"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_branding_tenant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Identity -------------------------------------------------------
    app_name: Mapped[str] = mapped_column(String(80), default="EquiMed")
    short_name: Mapped[str] = mapped_column(String(24), default="EquiMed")
    tagline: Mapped[str] = mapped_column(String(160), default="Distribution Suite")
    support_email: Mapped[str] = mapped_column(String(160), default="")
    support_url: Mapped[str] = mapped_column(String(255), default="")

    # --- Assets (data: URIs so a tenant needs no asset hosting) ---------
    logo_light_data_url: Mapped[str] = mapped_column(Text, default="")
    logo_dark_data_url: Mapped[str] = mapped_column(Text, default="")
    favicon_data_url: Mapped[str] = mapped_column(Text, default="")

    # --- Theme ----------------------------------------------------------
    # JSON objects of validated CSS custom-property overrides, keyed exactly as
    # in globals.css (e.g. {"--color-accent": "#0f766e"}).
    light_tokens_json: Mapped[str] = mapped_column(Text, default="{}")
    dark_tokens_json: Mapped[str] = mapped_column(Text, default="{}")
    font_heading: Mapped[str] = mapped_column(String(80), default="")
    font_body: Mapped[str] = mapped_column(String(80), default="")
    default_theme: Mapped[str] = mapped_column(String(10), default="system")

    # --- Dashboard composition -------------------------------------------
    # {"widgets": [{"id": ..., "viz": ..., "span": ..., "visible": ...}]}
    dashboard_layout_json: Mapped[str] = mapped_column(Text, default="{}")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
