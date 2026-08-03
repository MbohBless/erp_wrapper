"""App-DB access for per-tenant integration configuration."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.integration import KIND_PAYMENT, TenantIntegrationConfig
from utils.crypto import decrypt, decrypt_json, encrypt, encrypt_json


class IntegrationRepository:
    """Scoped to one tenant. Credentials are sealed on write and only opened
    by :meth:`credentials_for`, so a caller has to ask explicitly to see them."""

    def __init__(self, db: Session, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    # -- reads -------------------------------------------------------------
    def list(self, kind: str = KIND_PAYMENT) -> list[TenantIntegrationConfig]:
        return list(
            self.db.scalars(
                select(TenantIntegrationConfig)
                .where(
                    TenantIntegrationConfig.tenant_id == self.tenant_id,
                    TenantIntegrationConfig.kind == kind,
                )
                .order_by(TenantIntegrationConfig.provider)
            )
        )

    def get(self, provider: str, kind: str = KIND_PAYMENT) -> TenantIntegrationConfig | None:
        return self.db.scalar(
            select(TenantIntegrationConfig).where(
                TenantIntegrationConfig.tenant_id == self.tenant_id,
                TenantIntegrationConfig.kind == kind,
                TenantIntegrationConfig.provider == provider,
            )
        )

    def get_active(self, kind: str = KIND_PAYMENT) -> TenantIntegrationConfig | None:
        """The provider this tenant's payments route through, if any."""
        return self.db.scalar(
            select(TenantIntegrationConfig).where(
                TenantIntegrationConfig.tenant_id == self.tenant_id,
                TenantIntegrationConfig.kind == kind,
                TenantIntegrationConfig.is_active.is_(True),
            )
        )

    def credentials_for(self, config: TenantIntegrationConfig) -> dict:
        return decrypt_json(config.credentials_enc)

    def webhook_secret_for(self, config: TenantIntegrationConfig) -> str:
        return decrypt(config.webhook_secret_enc)

    @staticmethod
    def settings_for(config: TenantIntegrationConfig) -> dict:
        try:
            value = json.loads(config.settings_json or "{}")
        except (ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    # -- writes ------------------------------------------------------------
    def upsert(
        self,
        provider: str,
        *,
        kind: str = KIND_PAYMENT,
        mode: str | None = None,
        credentials: dict | None = None,
        webhook_secret: str | None = None,
        settings: dict | None = None,
        is_active: bool | None = None,
    ) -> TenantIntegrationConfig:
        config = self.get(provider, kind)
        if config is None:
            config = TenantIntegrationConfig(
                tenant_id=self.tenant_id, kind=kind, provider=provider
            )
            self.db.add(config)

        if mode is not None:
            config.mode = mode
        # ``None`` means "leave as-is" so a settings form can be saved without
        # re-entering secrets it never displays.
        if credentials is not None:
            config.credentials_enc = encrypt_json(credentials)
        if webhook_secret is not None:
            config.webhook_secret_enc = encrypt(webhook_secret)
        if settings is not None:
            config.settings_json = json.dumps(settings)
        if is_active is not None:
            config.is_active = is_active

        self.db.commit()
        self.db.refresh(config)
        return config

    def activate(self, provider: str, kind: str = KIND_PAYMENT) -> TenantIntegrationConfig | None:
        """Make one provider active and deactivate the rest.

        Exactly one active provider per kind: two would make it ambiguous which
        merchant account a collection should land in.
        """
        target = self.get(provider, kind)
        if target is None:
            return None
        for config in self.list(kind):
            config.is_active = config.provider == provider
        self.db.commit()
        self.db.refresh(target)
        return target

    def deactivate_all(self, kind: str = KIND_PAYMENT) -> None:
        for config in self.list(kind):
            config.is_active = False
        self.db.commit()

    def delete(self, provider: str, kind: str = KIND_PAYMENT) -> bool:
        config = self.get(provider, kind)
        if config is None:
            return False
        self.db.delete(config)
        self.db.commit()
        return True

    def delete_all(self) -> None:
        """Offboarding: drop every integration this tenant configured."""
        for config in self.db.scalars(
            select(TenantIntegrationConfig).where(
                TenantIntegrationConfig.tenant_id == self.tenant_id
            )
        ):
            self.db.delete(config)
        self.db.commit()
