"""Branding business logic: validated theme, assets and dashboard layout."""

from config import settings
from repositories.branding_repository import BrandingRepository
from schemas.branding import (
    DEFAULT_DASHBOARD,
    BrandingRead,
    BrandingUpdate,
    DashboardLayout,
    PublicBranding,
)


class BrandingService:
    def __init__(self, repo: BrandingRepository) -> None:
        self.repo = repo

    def _current(self) -> BrandingRead:
        data = self.repo.as_dict()
        # A tenant that has not customised its identity inherits the deployment's
        # brand from the environment. Empty means "never set", which is why the
        # columns default to blank rather than to a product name — otherwise
        # BRAND_APP_NAME could never take effect.
        data["app_name"] = data.get("app_name") or settings.brand_app_name
        data["short_name"] = (
            data.get("short_name") or settings.brand_short_name or data["app_name"][:24]
        )
        data["tagline"] = data.get("tagline") or settings.brand_tagline
        # An empty layout means "never customised" — serve the product default
        # rather than an empty dashboard.
        if not data.get("dashboard", {}).get("widgets"):
            data["dashboard"] = DEFAULT_DASHBOARD.model_dump()
        return BrandingRead.model_validate(data)

    def get(self) -> BrandingRead:
        return self._current()

    def update(self, data: BrandingUpdate) -> BrandingRead:
        self.repo.update(data.model_dump())
        return self._current()

    def reset_dashboard(self) -> BrandingRead:
        self.repo.update({"dashboard": DEFAULT_DASHBOARD.model_dump()})
        return self._current()

    def update_dashboard(self, layout: DashboardLayout) -> BrandingRead:
        self.repo.update({"dashboard": layout.model_dump()})
        return self._current()

    def public(self, tenant_id: str) -> PublicBranding:
        """The pre-login projection: enough to paint a branded sign-in page."""
        b = self._current()
        return PublicBranding(
            tenant=tenant_id,
            app_name=b.app_name,
            short_name=b.short_name,
            tagline=b.tagline,
            logo_light_data_url=b.logo_light_data_url,
            logo_dark_data_url=b.logo_dark_data_url,
            favicon_data_url=b.favicon_data_url,
            light_tokens=b.light_tokens,
            dark_tokens=b.dark_tokens,
            font_heading=b.font_heading,
            font_body=b.font_body,
            default_theme=b.default_theme,
        )
