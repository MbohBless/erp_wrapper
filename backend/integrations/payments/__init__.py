"""Mobile-money providers, and the factory that picks one.

Every module here implements :class:`~integrations.payments.base.PaymentProvider`
against one provider's published API. Nothing above this package knows a
provider's vocabulary — swapping CamPay for a direct MTN integration is a
configuration change, not a code change.

Providers are constructed **per request from the tenant's own credentials**. The
tenant owns the merchant account; EquiMed never holds customer funds. See
``docs/payments.md`` for why that boundary is not negotiable.
"""

from typing import Any, Callable

from integrations.payments.base import (
    CollectionRequest,
    PaymentProvider,
    PaymentProviderError,
    PaymentStatus,
    PayoutRequest,
    ProviderConfigError,
    ProviderIntent,
    ProviderStatusResult,
    ProviderUnavailable,
    WebhookHint,
    local_msisdn,
    normalise_msisdn,
)
from integrations.payments.campay import CamPayProvider
from integrations.payments.fake import FakePaymentProvider
from integrations.payments.fapshi import FapshiProvider
from integrations.payments.mtn_momo import MtnMomoProvider

# Registry. Keys match models.integration.PAYMENT_PROVIDERS.
_REGISTRY: dict[str, Callable[..., PaymentProvider]] = {
    "fake": FakePaymentProvider,
    "campay": CamPayProvider,
    "fapshi": FapshiProvider,
    "mtn_momo": MtnMomoProvider,
}

# Which credential fields each provider needs, for validation and for rendering
# the settings form without the frontend hardcoding provider knowledge.
CREDENTIAL_FIELDS: dict[str, tuple[str, ...]] = {
    "fake": (),
    "campay": ("app_username", "app_password"),
    "fapshi": ("apiuser", "apikey"),
    "mtn_momo": ("api_user", "api_key", "collection_subscription_key"),
}

OPTIONAL_CREDENTIAL_FIELDS: dict[str, tuple[str, ...]] = {
    "fake": (),
    "campay": (),
    # Fapshi disables collection on a service once payouts are enabled, so a
    # tenant doing both holds two services.
    "fapshi": ("payout_apiuser", "payout_apikey"),
    "mtn_momo": ("disbursement_subscription_key", "target_environment"),
}


def available_providers() -> tuple[str, ...]:
    return tuple(_REGISTRY)


def build_provider(
    provider: str, credentials: dict[str, Any], *, mode: str = "sandbox"
) -> PaymentProvider:
    """Construct a provider client from a tenant's stored credentials.

    Raises :class:`ProviderConfigError` for an unknown provider or missing
    credentials — both are configuration mistakes a retry cannot fix.
    """
    factory = _REGISTRY.get(provider)
    if factory is None:
        raise ProviderConfigError(
            f"Unknown payment provider '{provider}'. "
            f"Available: {', '.join(sorted(_REGISTRY))}."
        )
    missing = [
        field
        for field in CREDENTIAL_FIELDS.get(provider, ())
        if not str(credentials.get(field) or "").strip()
    ]
    if missing:
        raise ProviderConfigError(
            f"{provider} is missing credential(s): {', '.join(missing)}."
        )
    return factory(credentials, mode=mode)


__all__ = [
    "CREDENTIAL_FIELDS",
    "OPTIONAL_CREDENTIAL_FIELDS",
    "CamPayProvider",
    "CollectionRequest",
    "FakePaymentProvider",
    "FapshiProvider",
    "MtnMomoProvider",
    "PaymentProvider",
    "PaymentProviderError",
    "PaymentStatus",
    "PayoutRequest",
    "ProviderConfigError",
    "ProviderIntent",
    "ProviderStatusResult",
    "ProviderUnavailable",
    "WebhookHint",
    "available_providers",
    "build_provider",
    "local_msisdn",
    "normalise_msisdn",
]
