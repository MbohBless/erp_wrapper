"""An in-memory provider that behaves like a real one, minus the network.

This is the default provider and it carries real weight: without live
credentials it is the only way to exercise the paths that actually break in
production — a payer who never confirms, a duplicate callback, a provider that
reports a different amount than we asked for.

Behaviour is driven by the **payer's number**, mirroring how real sandboxes
work, so failure paths can be walked from the UI without editing code:

===================  ==========================================================
Number ends in       Behaviour
===================  ==========================================================
``0000``             fails on first status check
``9999``             never leaves pending (the payer walked away)
``1111``             succeeds, but for a *different amount* than requested
``2222``             provider is down — raises ``ProviderUnavailable``
anything else        pending on initiation, then succeeds
===================  ==========================================================

State is **process-wide**, not per-instance. A provider is constructed fresh on
every request from the tenant's stored credentials, so instance state would be
discarded between initiating a payment and checking it — exactly the bug a fake
should not have. Keeping transactions in a module-level store makes the fake
behave the way a real provider does: the state lives outside the client.

Call :meth:`FakePaymentProvider.reset` between tests that need isolation.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from integrations.payments.base import (
    CollectionRequest,
    PayoutRequest,
    PaymentStatus,
    ProviderIntent,
    ProviderStatusResult,
    ProviderUnavailable,
    WebhookHint,
    normalise_msisdn,
)

SUFFIX_FAIL = "0000"
SUFFIX_STUCK = "9999"
SUFFIX_WRONG_AMOUNT = "1111"
SUFFIX_UNAVAILABLE = "2222"


@dataclass
class _FakeTransaction:
    provider_ref: str
    reference: str
    amount: int
    currency: str
    msisdn: str
    direction: str
    status: PaymentStatus = PaymentStatus.PENDING
    polls: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


# Shared by every instance in the process — see the module docstring.
_TRANSACTIONS: dict[str, _FakeTransaction] = {}
_CALLS: list[tuple[str, str]] = []


class FakePaymentProvider:
    name = "fake"
    supports_webhook_verification = True

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        *,
        mode: str = "sandbox",
        # How many status checks a transaction stays pending before settling.
        # Raise it to reproduce a payer who takes their time.
        settle_after_polls: int = 0,
    ) -> None:
        self.mode = mode
        self.settle_after_polls = settle_after_polls
        self.transactions = _TRANSACTIONS
        self.calls = _CALLS
        self._credentials = credentials or {}

    @classmethod
    def reset(cls) -> None:
        """Forget every simulated transaction (test isolation)."""
        _TRANSACTIONS.clear()
        _CALLS.clear()

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _suffix(msisdn: str) -> str:
        digits = normalise_msisdn(msisdn)
        return digits[-4:] if len(digits) >= 4 else ""

    def _guard_unavailable(self, msisdn: str) -> None:
        if self._suffix(msisdn) == SUFFIX_UNAVAILABLE:
            raise ProviderUnavailable("Fake provider is simulating an outage.")

    def _record(self, request, msisdn: str, direction: str) -> ProviderIntent:
        self._guard_unavailable(msisdn)
        # Same reference twice returns the same transaction — real providers
        # dedupe on external id and so must the fake, or tests would not catch
        # a missing idempotency guard.
        for existing in self.transactions.values():
            if existing.reference == request.reference:
                return ProviderIntent(
                    provider_ref=existing.provider_ref,
                    status=PaymentStatus.PENDING,
                    provider_status="PENDING",
                    raw=existing.raw,
                )

        provider_ref = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fake:{request.reference}"))
        transaction = _FakeTransaction(
            provider_ref=provider_ref,
            reference=request.reference,
            amount=request.amount,
            currency=request.currency,
            msisdn=normalise_msisdn(msisdn),
            direction=direction,
            raw={"provider_ref": provider_ref, "external_reference": request.reference},
        )
        self.transactions[provider_ref] = transaction
        self.calls.append((direction, request.reference))
        return ProviderIntent(
            provider_ref=provider_ref,
            status=PaymentStatus.PENDING,
            provider_status="PENDING",
            ussd_code="*126#",
            operator="FAKE",
            payment_url=(
                f"https://fake.local/pay/{provider_ref}"
                if getattr(request, "hosted", False)
                else ""
            ),
            raw=transaction.raw,
        )

    # -- operations --------------------------------------------------------
    async def collect(self, request: CollectionRequest) -> ProviderIntent:
        return self._record(request, request.payer_msisdn, "collection")

    async def payout(self, request: PayoutRequest) -> ProviderIntent:
        return self._record(request, request.payee_msisdn, "payout")

    async def get_status(
        self, provider_ref: str, *, direction: str = "collection"  # noqa: ARG002
    ) -> ProviderStatusResult:
        transaction = self.transactions.get(provider_ref)
        if transaction is None:
            return ProviderStatusResult(
                provider_ref=provider_ref, status=PaymentStatus.UNKNOWN
            )

        self._guard_unavailable(transaction.msisdn)
        transaction.polls += 1
        suffix = self._suffix(transaction.msisdn)

        if suffix == SUFFIX_STUCK:
            status = PaymentStatus.PENDING
        elif transaction.polls <= self.settle_after_polls:
            status = PaymentStatus.PENDING
        elif suffix == SUFFIX_FAIL:
            status = PaymentStatus.FAILED
        else:
            status = PaymentStatus.SUCCEEDED
        transaction.status = status

        # A provider reporting a different amount than we asked for is rare but
        # real, and must never be posted to the ledger silently.
        reported = transaction.amount
        if suffix == SUFFIX_WRONG_AMOUNT and status is PaymentStatus.SUCCEEDED:
            reported = max(transaction.amount - 100, 1)

        return ProviderStatusResult(
            provider_ref=provider_ref,
            status=status,
            provider_status=status.value.upper(),
            amount=reported,
            currency=transaction.currency,
            operator="FAKE",
            operator_ref=f"FAKEOP-{transaction.polls}",
            failure_reason="Simulated failure" if status is PaymentStatus.FAILED else "",
            raw={"provider_ref": provider_ref, "status": status.value},
        )

    async def get_balance(self) -> dict:
        return {"total_balance": 0, "currency": "XAF"}

    # -- webhook -----------------------------------------------------------
    def parse_webhook(
        self, headers: dict[str, str], raw_body: bytes, webhook_secret: str
    ) -> WebhookHint:
        import json
        import secrets as _secrets

        try:
            body = json.loads(raw_body or b"{}")
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}

        supplied = next(
            (v for k, v in headers.items() if k.lower() == "x-fake-signature"), ""
        )
        verified = bool(
            webhook_secret and _secrets.compare_digest(supplied or "", webhook_secret)
        )
        provider_ref = str(body.get("provider_ref") or "")
        return WebhookHint(
            event_key=provider_ref,
            provider_ref=provider_ref,
            our_reference=str(body.get("external_reference") or ""),
            claimed_status=str(body.get("status") or ""),
            verified=verified,
            raw=body,
        )
