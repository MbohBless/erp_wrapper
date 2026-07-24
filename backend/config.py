"""Application configuration (Pydantic V2 settings).

Loaded from environment variables (see docker-compose.yml) or a local .env file.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "Medical ERP API"
    version: str = "0.1.0"
    # Mounted behind the reverse proxy at /api; keeps OpenAPI/docs URLs correct.
    root_path: str = "/api"
    cors_origins: list[str] = ["*"]

    # --- Database (FastAPI's own store for users / auth / RBAC) ---
    # ERPNext keeps the business/accounting data; this DB is app-auth only.
    database_url: str = "sqlite:////app/data/app.db"

    # --- Auth / JWT ---
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

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
