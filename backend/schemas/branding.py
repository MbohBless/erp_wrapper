"""Branding schemas — and the validation that makes theming safe.

Tenant-supplied theme values are rendered into a ``<style>`` block on every
page. That is a CSS-injection surface, so nothing here accepts free text:

* token **names** must be in :data:`THEME_TOKENS` (the tokens globals.css
  actually defines),
* token **values** must be a plain hex colour,
* **fonts** must match a conservative family-name pattern — no ``url()``,
  no quotes, no semicolons, so a value cannot escape its declaration,
* **assets** must be ``data:image/...`` URIs, so branding can never point the
  browser at a third-party host.

Reject rather than sanitise: a silently-mangled brand colour is a support
ticket, while a silently-accepted payload is a vulnerability.
"""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Theme tokens ---------------------------------------------------------
# Mirrors the custom properties declared in frontend/app/globals.css. Adding a
# token here is what makes it themable; nothing else needs to change.
THEME_TOKENS: frozenset[str] = frozenset(
    {
        "--color-bg",
        "--color-surface",
        "--color-text",
        "--color-accent",
        "--color-accent-600",
        "--color-accent-700",
        "--ok",
        "--warn",
        "--err",
        "--ok-raw",
        "--warn-raw",
        "--err-raw",
    }
)

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
# Letters, digits, spaces and hyphens only — enough for "IBM Plex Sans",
# not enough for `url(...)`, `;`, `}` or a comment sequence.
_FONT_FAMILY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{0,48}$")
_DATA_IMAGE = re.compile(r"^data:image/(png|jpeg|jpg|svg\+xml|webp);base64,[A-Za-z0-9+/=\s]+$")

# 512 KB of base64 is a generous logo and a cheap ceiling on row size.
MAX_ASSET_CHARS = 512 * 1024


def _validate_tokens(value: dict[str, str] | None) -> dict[str, str]:
    if not value:
        return {}
    unknown = sorted(set(value) - THEME_TOKENS)
    if unknown:
        raise ValueError(
            f"Unknown theme token(s): {', '.join(unknown)}. "
            f"Allowed: {', '.join(sorted(THEME_TOKENS))}"
        )
    for name, raw in value.items():
        if not isinstance(raw, str) or not _HEX_COLOR.match(raw.strip()):
            raise ValueError(f"{name} must be a hex colour such as #0f766e")
    return {k: v.strip() for k, v in value.items()}


def _validate_asset(value: str | None) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) > MAX_ASSET_CHARS:
        raise ValueError("Image is too large (max 512 KB encoded)")
    if not _DATA_IMAGE.match(value):
        raise ValueError("Image must be an inline data:image/... base64 URI")
    return value


def _validate_font(value: str | None) -> str:
    value = (value or "").strip()
    if value and not _FONT_FAMILY.match(value):
        raise ValueError(
            "Font family may contain letters, digits, spaces and hyphens only"
        )
    return value


# --- Dashboard layout -----------------------------------------------------
# The catalogue of widgets a tenant may compose a dashboard from. The frontend
# renders by id, so an unknown id here is a 422 rather than a blank panel.
WidgetId = Literal[
    "kpi.revenue",
    "kpi.inventory_value",
    "kpi.receivables",
    "kpi.payables",
    "chart.revenue_trend",
    "chart.segment_mix",
    "list.low_stock",
    "list.expiring",
    "table.recent_sales",
    "feed.activity",
]

VizType = Literal["line", "area", "bar", "stacked-bar", "donut", "progress"]

# Which visualisations each widget can legitimately render as. Enforced so a
# KPI tile cannot be configured as a donut chart of one number.
WIDGET_VIZ: dict[str, tuple[str, ...]] = {
    "chart.revenue_trend": ("line", "area", "bar"),
    "chart.segment_mix": ("donut", "progress", "stacked-bar"),
}


class DashboardWidget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: WidgetId
    visible: bool = True
    # Grid columns out of 4; the frontend clamps responsively.
    span: Annotated[int, Field(ge=1, le=4)] = 1
    viz: VizType | None = None
    title: Annotated[str, Field(max_length=60)] | None = None

    @field_validator("viz")
    @classmethod
    def _viz_allowed_for_widget(cls, v: str | None, info) -> str | None:
        if v is None:
            return v
        widget_id = info.data.get("id")
        allowed = WIDGET_VIZ.get(str(widget_id), ())
        if not allowed:
            raise ValueError(f"Widget '{widget_id}' does not support a viz type")
        if v not in allowed:
            raise ValueError(
                f"Widget '{widget_id}' supports viz: {', '.join(allowed)}"
            )
        return v


class DashboardLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    widgets: Annotated[list[DashboardWidget], Field(max_length=32)] = []

    @field_validator("widgets")
    @classmethod
    def _no_duplicate_widgets(cls, v: list[DashboardWidget]) -> list[DashboardWidget]:
        seen = [w.id for w in v]
        dupes = sorted({i for i in seen if seen.count(i) > 1})
        if dupes:
            raise ValueError(f"Duplicate widget(s): {', '.join(dupes)}")
        return v


DEFAULT_DASHBOARD = DashboardLayout(
    widgets=[
        DashboardWidget(id="kpi.revenue", span=1),
        DashboardWidget(id="kpi.inventory_value", span=1),
        DashboardWidget(id="kpi.receivables", span=1),
        DashboardWidget(id="kpi.payables", span=1),
        DashboardWidget(id="chart.revenue_trend", span=3, viz="area"),
        DashboardWidget(id="chart.segment_mix", span=1, viz="progress"),
        DashboardWidget(id="list.low_stock", span=2),
        DashboardWidget(id="list.expiring", span=2),
        DashboardWidget(id="table.recent_sales", span=3),
        DashboardWidget(id="feed.activity", span=1),
    ]
)


# --- Read / update models -------------------------------------------------
class BrandingBase(BaseModel):
    app_name: Annotated[str, Field(max_length=80)] = ""
    short_name: Annotated[str, Field(max_length=24)] = ""
    tagline: Annotated[str, Field(max_length=160)] = ""
    support_email: Annotated[str, Field(max_length=160)] = ""
    support_url: Annotated[str, Field(max_length=255)] = ""
    logo_light_data_url: str = ""
    logo_dark_data_url: str = ""
    favicon_data_url: str = ""
    light_tokens: dict[str, str] = {}
    dark_tokens: dict[str, str] = {}
    font_heading: str = ""
    font_body: str = ""
    default_theme: Literal["light", "dark", "system"] = "system"
    dashboard: DashboardLayout = DEFAULT_DASHBOARD

    @field_validator("light_tokens", "dark_tokens")
    @classmethod
    def _check_tokens(cls, v: dict[str, str]) -> dict[str, str]:
        return _validate_tokens(v)

    @field_validator("logo_light_data_url", "logo_dark_data_url", "favicon_data_url")
    @classmethod
    def _check_assets(cls, v: str) -> str:
        return _validate_asset(v)

    @field_validator("font_heading", "font_body")
    @classmethod
    def _check_fonts(cls, v: str) -> str:
        return _validate_font(v)


class BrandingRead(BrandingBase):
    """Full branding, returned to authenticated callers and the settings UI."""


class BrandingUpdate(BrandingBase):
    """Same shape as read: branding is edited as a whole document."""


class PublicBranding(BaseModel):
    """Unauthenticated projection, served before sign-in.

    Only what is needed to paint the login screen and the document head. No
    support addresses, no dashboard layout — those require a session.
    """

    tenant: str
    app_name: str
    short_name: str
    tagline: str
    logo_light_data_url: str
    logo_dark_data_url: str
    favicon_data_url: str
    light_tokens: dict[str, str]
    dark_tokens: dict[str, str]
    font_heading: str
    font_body: str
    default_theme: str
