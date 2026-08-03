"""The payment-provider contract.

Every mobile-money provider we support is reduced to this interface so the
service layer never learns a provider's vocabulary. Adding a provider means one
new module here — nothing above it changes.

Three rules shape the design:

**Webhooks are hints, never truth.** A callback tells us *something happened*;
it never tells us *what* is true. Providers differ wildly in how (or whether)
they authenticate callbacks — Fapshi sends a shared secret header, MTN sends
nothing at all — so a forged callback must not be able to mark an invoice paid.
:meth:`PaymentProvider.parse_webhook` therefore returns only enough to identify
the transaction, and the service re-confirms through :meth:`get_status` before
a single line reaches the ledger. This also means an unverifiable provider is
still safe to enable.

**Money is integers.** XAF has no minor unit. Amounts are whole currency units;
nothing here accepts a float.

**Initiation is not confirmation.** Every provider returns "accepted" long
before the customer has approved anything on their handset. Initiating returns
``pending``, and only a status confirmation moves an intent to ``succeeded``.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class PaymentProviderError(RuntimeError):
    """A provider call failed. Carries whether retrying could plausibly help."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ProviderConfigError(PaymentProviderError):
    """Credentials are missing or malformed — retrying will not help."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)


class ProviderUnavailable(PaymentProviderError):
    """The provider is unreachable or returned 5xx — safe to retry."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=True)


class PaymentStatus(str, Enum):
    """Normalised lifecycle, mapped from each provider's own vocabulary."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    # The provider has no record of this reference. Distinct from FAILED: a
    # hosted-checkout link that nobody has opened yet reports UNKNOWN, and
    # treating that as failure would cancel live payments.
    UNKNOWN = "unknown"

    @property
    def is_terminal(self) -> bool:
        return self in (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED, PaymentStatus.EXPIRED)


@dataclass(frozen=True, slots=True)
class CollectionRequest:
    """Ask a customer to pay. ``reference`` is ours and is passed to the
    provider as its external id, which is what makes retries idempotent."""

    reference: str
    amount: int
    currency: str = "XAF"
    payer_msisdn: str = ""          # 2376XXXXXXXX
    payer_name: str = ""
    payer_email: str = ""
    description: str = ""
    # Hosted checkout instead of a direct handset prompt. Needed when we do not
    # hold the payer's number (an emailed invoice link, say).
    hosted: bool = False
    redirect_url: str = ""
    failure_redirect_url: str = ""


@dataclass(frozen=True, slots=True)
class PayoutRequest:
    """Send money out — settling a supplier bill or refunding a customer."""

    reference: str
    amount: int
    currency: str = "XAF"
    payee_msisdn: str = ""
    payee_name: str = ""
    payee_email: str = ""
    description: str = ""


@dataclass(frozen=True, slots=True)
class ProviderIntent:
    """What a provider returns when a transfer is accepted for processing."""

    provider_ref: str
    status: PaymentStatus = PaymentStatus.PENDING
    provider_status: str = ""
    payment_url: str = ""
    ussd_code: str = ""
    operator: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderStatusResult:
    """The authoritative answer to "did this money actually move?"."""

    provider_ref: str
    status: PaymentStatus
    provider_status: str = ""
    amount: int | None = None
    currency: str = ""
    operator: str = ""
    operator_ref: str = ""
    failure_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WebhookHint:
    """The little we are willing to believe from an inbound callback.

    Deliberately does not carry an amount: accepting an amount from an
    unauthenticated callback is how you get charged for someone else's payment.
    ``claimed_status`` is recorded for debugging and never acted on directly.
    """

    event_key: str
    provider_ref: str = ""
    our_reference: str = ""
    claimed_status: str = ""
    verified: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(Protocol):
    """Implemented once per provider in this package."""

    name: str
    #: False when the provider cannot authenticate its callbacks (e.g. MTN).
    #: Purely informational — the service re-confirms status regardless.
    supports_webhook_verification: bool

    async def collect(self, request: CollectionRequest) -> ProviderIntent:
        """Request money from a payer. Returns as soon as it is accepted."""
        ...

    async def payout(self, request: PayoutRequest) -> ProviderIntent:
        """Send money to a payee. Returns as soon as it is accepted."""
        ...

    async def get_status(
        self, provider_ref: str, *, direction: str = "collection"
    ) -> ProviderStatusResult:
        """Authoritative status. The only thing allowed to confirm a payment."""
        ...

    def parse_webhook(
        self, headers: dict[str, str], raw_body: bytes, webhook_secret: str
    ) -> WebhookHint:
        """Identify the transaction a callback refers to, and say whether the
        callback authenticated. Must not raise on malformed input — return an
        unverified hint so the delivery is still recorded."""
        ...


def normalise_msisdn(value: str, country_code: str = "237") -> str:
    """Reduce a phone number to digits in international format.

    Cameroonian numbers are written every possible way — ``+237 6 77 00 00 00``,
    ``677000000``, ``00237677000000``. Providers accept only one, and getting
    this wrong means paying the wrong person, so normalisation is central rather
    than per-provider.
    """
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith(country_code):
        return digits
    # A bare national number (6XXXXXXXX in Cameroon) gains the country code.
    return f"{country_code}{digits.lstrip('0')}"


def local_msisdn(value: str, country_code: str = "237") -> str:
    """The national form some providers insist on (Fapshi wants 67XXXXXXX)."""
    digits = normalise_msisdn(value, country_code)
    return digits[len(country_code):] if digits.startswith(country_code) else digits
