"""Managing a tenant's third-party integration credentials.

Kept separate from :mod:`services.payment_gateway_service` because the two have
different audiences and different risk: this one is an occasional settings
operation performed by an administrator, that one runs on every payment.

The rule enforced throughout: **credentials go in and never come out.** Reads
report which fields hold a value, never the values.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from integrations.payments import (
    CREDENTIAL_FIELDS,
    OPTIONAL_CREDENTIAL_FIELDS,
    available_providers,
    build_provider,
)
from integrations.payments.base import ProviderConfigError
from models.integration import KIND_PAYMENT, TenantIntegrationConfig
from repositories.integration_repository import IntegrationRepository
from schemas.gateway import (
    ProviderCatalogEntry,
    ProviderConfigRead,
    ProviderConfigUpsert,
)
from utils.crypto import SecretUnreadable


class IntegrationService:
    def __init__(self, repo: IntegrationRepository) -> None:
        self.repo = repo

    # -- catalogue ---------------------------------------------------------
    @staticmethod
    def catalog() -> list[ProviderCatalogEntry]:
        """What the settings form needs in order to render itself.

        Served from the backend so the frontend does not hardcode provider
        knowledge — adding a provider stays a one-directory change.
        """
        entries: list[ProviderCatalogEntry] = []
        for name in available_providers():
            try:
                supports = build_provider(
                    name,
                    {field: "x" for field in CREDENTIAL_FIELDS.get(name, ())},
                ).supports_webhook_verification
            except ProviderConfigError:
                supports = False
            entries.append(
                ProviderCatalogEntry(
                    provider=name,
                    required_fields=list(CREDENTIAL_FIELDS.get(name, ())),
                    optional_fields=list(OPTIONAL_CREDENTIAL_FIELDS.get(name, ())),
                    supports_webhook_verification=supports,
                )
            )
        return entries

    # -- reads -------------------------------------------------------------
    def _read(self, config: TenantIntegrationConfig) -> ProviderConfigRead:
        try:
            credentials = self.repo.credentials_for(config)
            configured = sorted(k for k, v in credentials.items() if v)
        except SecretUnreadable:
            # The encryption key changed. Say so plainly rather than showing an
            # empty form that looks like nothing was ever configured.
            configured = []
        supports = True
        try:
            supports = build_provider(
                config.provider,
                {f: "x" for f in CREDENTIAL_FIELDS.get(config.provider, ())},
            ).supports_webhook_verification
        except ProviderConfigError:
            pass

        return ProviderConfigRead(
            provider=config.provider,
            mode=config.mode,
            is_active=config.is_active,
            configured_fields=configured,
            required_fields=list(CREDENTIAL_FIELDS.get(config.provider, ())),
            optional_fields=list(OPTIONAL_CREDENTIAL_FIELDS.get(config.provider, ())),
            webhook_secret_set=bool(config.webhook_secret_enc),
            supports_webhook_verification=supports,
            settings=self.repo.settings_for(config),
            updated_at=config.updated_at,
        )

    def list(self) -> list[ProviderConfigRead]:
        return [self._read(config) for config in self.repo.list(KIND_PAYMENT)]

    def get(self, provider: str) -> ProviderConfigRead:
        config = self.repo.get(provider, KIND_PAYMENT)
        if config is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"'{provider}' is not configured."
            )
        return self._read(config)

    # -- writes ------------------------------------------------------------
    def upsert(self, data: ProviderConfigUpsert) -> ProviderConfigRead:
        existing = self.repo.get(data.provider, KIND_PAYMENT)
        merged = dict(self.repo.credentials_for(existing)) if existing else {}
        if data.credentials:
            merged.update(data.credentials)

        # Validate before storing: a credential set that cannot construct a
        # provider is a configuration error the admin should see now, not the
        # first time a customer tries to pay.
        if merged or data.activate:
            try:
                build_provider(data.provider, merged, mode=data.mode)
            except ProviderConfigError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)
                ) from exc

        config = self.repo.upsert(
            data.provider,
            mode=data.mode,
            credentials=merged if data.credentials is not None else None,
            webhook_secret=data.webhook_secret,
            settings=data.settings,
        )
        if data.activate:
            config = self.repo.activate(data.provider, KIND_PAYMENT) or config
        return self._read(config)

    def activate(self, provider: str) -> ProviderConfigRead:
        config = self.repo.get(provider, KIND_PAYMENT)
        if config is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"'{provider}' is not configured."
            )
        try:
            build_provider(
                provider, self.repo.credentials_for(config), mode=config.mode
            )
        except ProviderConfigError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        return self._read(self.repo.activate(provider, KIND_PAYMENT) or config)

    def deactivate_all(self) -> list[ProviderConfigRead]:
        """Stop routing payments anywhere — the tenant-level kill switch."""
        self.repo.deactivate_all(KIND_PAYMENT)
        return self.list()

    def delete(self, provider: str) -> None:
        if not self.repo.delete(provider, KIND_PAYMENT):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"'{provider}' is not configured."
            )
