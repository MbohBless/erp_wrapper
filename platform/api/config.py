"""Control-plane configuration.

Deliberately a separate Settings class from the tenant app's: the control plane
owns the tenant registry and can suspend every customer at once, so it must not
inherit a single misconfigured value from an app-level .env.

The signing key in particular is separate on purpose — see
:func:`Settings.check_key_separation`.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "EquiMed Control Plane"
    version: str = "0.1.0"
    root_path: str = "/platform-api"
    cors_origins: list[str] = ["*"]

    # --- Database (registry, plans, platform operators, audit) ---
    database_url: str = "sqlite:////app/data/platform.db"

    # --- Auth (platform operators — NOT tenant users) ---
    jwt_secret_key: str = "CHANGE_ME_PLATFORM_SECRET"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # Secret used to encrypt tenant ERPNext credentials at rest. Derived from
    # the JWT secret when unset so a dev install works, but set it explicitly
    # in production: rotating the JWT key would otherwise orphan every secret.
    secret_encryption_key: str = ""

    # --- Initial platform owner (seeded on first start) ---
    first_owner_email: str = "owner@equimed.app"
    first_owner_password: str = "changeme12345"
    first_owner_name: str = "Platform Owner"

    # --- Talking to tenant app instances ---
    # Shared secret for POST /internal/* on the tenant backend.
    internal_api_token: str = ""
    # Default tenant-app base URL used for bootstrap/purge callbacks.
    tenant_app_url: str = "http://backend:8000"

    # --- Tenant defaults ---
    base_domain: str = "equimed.app"
    default_erpnext_url: str = "http://erpnext-nginx:8080"
    # Frappe multi-site: tenant sites are "<slug>.<this suffix>".
    erpnext_site_suffix: str = "erp.local"

    # --- Provisioning ---
    # "noop"  - record intent only (dev, tests, and manual provisioning)
    # "bench" - shell out to a Frappe bench to create/drop sites
    provisioner: str = "noop"
    bench_container: str = "erpnext-backend"
    provision_timeout_seconds: int = 900

    def check_key_separation(self) -> list[str]:
        """Return configuration warnings worth failing a deploy review over."""
        warnings: list[str] = []
        if self.jwt_secret_key.startswith("CHANGE_ME"):
            warnings.append("PLATFORM_JWT_SECRET_KEY is still the default value.")
        if not self.internal_api_token:
            warnings.append(
                "INTERNAL_API_TOKEN is unset — tenant provisioning callbacks "
                "will fail closed."
            )
        if not self.secret_encryption_key:
            warnings.append(
                "SECRET_ENCRYPTION_KEY is unset — tenant ERPNext credentials "
                "are encrypted with a key derived from the JWT secret; "
                "rotating that secret would make them unreadable."
            )
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
