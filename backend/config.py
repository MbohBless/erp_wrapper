"""Application configuration (Pydantic V2 settings).

Loaded from environment variables (see docker-compose.yml) or a local .env file.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "Medical ERP API"
    version: str = "0.1.0"
    # Mounted behind the reverse proxy at /api; keeps OpenAPI/docs URLs correct.
    root_path: str = "/api"
    cors_origins: list[str] = ["*"]

    # --- Brand defaults --------------------------------------------------
    # What the product calls itself before a tenant customises it in Settings.
    # Env-configurable so a self-hosted or dedicated install shows the right
    # name from first boot, with no database edit. A tenant's saved branding
    # always wins over these.
    brand_app_name: str = "EquiMed"
    brand_short_name: str = ""          # falls back to brand_app_name
    brand_tagline: str = "Distribution Suite"

    # --- Roles -----------------------------------------------------------
    # Roles this deployment does not use, by name — e.g. DISABLED_ROLES=Sales
    # for a workspace whose accountant raises the invoices.
    #
    # A *deployment* setting rather than a code change, because the product is
    # multi-tenant: one workspace having no sales reps is no reason for the next
    # one to lose the option. Disabled means "cannot be assigned to anyone"; the
    # role keeps its permissions and its tests, so re-enabling it is a config
    # edit rather than a restoration.
    disabled_roles: list[str] = []

    # --- Tenancy ---------------------------------------------------------
    # "single": self-hosted / dedicated instance. One implicit tenant, no
    #           control plane, ERPNext coordinates come from this file.
    # "multi":  shared SaaS plane. The tenant is resolved per request from the
    #           Host header via the control plane; ERPNext coordinates come
    #           from the tenant record.
    tenancy_mode: Literal["single", "multi"] = "single"

    # Single-tenant identity (also the fallback tenant id used by migrations).
    default_tenant_id: str = "default"
    default_tenant_name: str = "EquiMed"

    # Multi-tenant: the control plane that owns the tenant registry.
    control_plane_url: str = "http://platform-api:8000"
    control_plane_token: str = ""
    # Resolved tenants are cached in-process for this long (seconds). Keep it
    # short: it is also how long a suspension takes to take effect.
    tenant_cache_ttl: int = 30
    # Host suffix for tenant subdomains, e.g. "clienta.equimed.app".
    base_domain: str = "equimed.app"

    # Shared secret guarding /internal/* (control-plane -> tenant app calls).
    internal_api_token: str = ""

    # --- Database (FastAPI's own store for users / auth / RBAC) ---
    # ERPNext keeps the business/accounting data; this DB is app-auth only.
    database_url: str = "sqlite:////app/data/app.db"

    # --- Auth / JWT ---
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Log level and shape. JSON by default because these are read by a log
    # processor far more often than by a person; LOG_FORMAT=text for dev.
    # Long enough that a working day does not interrupt a user, short enough
    # that a stolen refresh token is not indefinite. Rotation on every use
    # means a theft is usually detected long before this.
    refresh_token_expire_days: int = 30
    log_level: str = "INFO"
    log_format: str = "json"

    # --- Initial administrator (seeded on startup if it does not exist) ---
    first_admin_email: str = "admin@equimed.cm"
    first_admin_password: str = "admin12345"
    first_admin_name: str = "Administrator"

    # --- ERPNext integration ---
    # All ERPNext communication goes through integrations/erpnext.py.
    erpnext_url: str = "http://erpnext-nginx:8080"
    erpnext_api_key: str = ""
    erpnext_api_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    """FastAPI dependency: cached settings instance."""
    return Settings()


settings = get_settings()
