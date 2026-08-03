"""Mobile-money orchestration: request money, send money, post it to the ledger.

The rules this service exists to enforce, in order of how much damage breaking
them would do:

1. **Confirm before posting.** Nothing reaches the ledger on the strength of a
   webhook. A callback only tells us *which* transaction to go and ask about;
   the provider's status endpoint is the only thing allowed to say "paid".
   That holds even for providers that sign their callbacks, and it is what
   makes an unauthenticated provider (MTN) safe to enable at all.

2. **Idempotency at both ends.** A retried callback is recorded once
   (``webhook_event``), and a re-clicked "request payment" reuses the in-flight
   intent instead of charging twice.

3. **A mismatch is a review, not a guess.** If the provider settles a different
   amount than we asked for, the money is real but the posting is not obvious —
   so the intent is flagged for a human rather than posted approximately.

4. **Money arriving and money being booked are separate facts.** ERPNext being
   down must not lose a payment; the intent stays ``succeeded`` /
   ``reconciliation=pending`` and is picked up by the next sweep.
"""

import json
import uuid
from datetime import date

from fastapi import HTTPException, status as http_status

from integrations.erpnext import ERPNextError
from integrations.payments import (
    CollectionRequest,
    PaymentProvider,
    PaymentProviderError,
    PaymentStatus,
    PayoutRequest,
    ProviderConfigError,
    build_provider,
    normalise_msisdn,
)
from integrations.payments.base import ProviderStatusResult, WebhookHint
from models.integration import KIND_PAYMENT, TenantIntegrationConfig
from models.payment_intent import (
    DIRECTION_COLLECTION,
    DIRECTION_PAYOUT,
    RECON_NEEDS_REVIEW,
    RECON_NOT_APPLICABLE,
    RECON_PENDING,
    RECON_POSTED,
    STATUS_CREATED,
    STATUS_EXPIRED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SUCCEEDED,
    PaymentIntent,
)
from models.webhook_event import (
    OUTCOME_DUPLICATE,
    OUTCOME_ERROR,
    OUTCOME_UNKNOWN_INTENT,
)
from repositories.integration_repository import IntegrationRepository
from repositories.payment_intent_repository import PaymentIntentRepository
from repositories.payment_repository import PaymentRepository
from repositories.webhook_event_repository import WebhookEventRepository
from schemas.gateway import CollectionCreate, PayoutCreate, SweepResult

_STATUS_TO_INTENT = {
    PaymentStatus.PENDING: STATUS_PENDING,
    PaymentStatus.SUCCEEDED: STATUS_SUCCEEDED,
    PaymentStatus.FAILED: STATUS_FAILED,
    PaymentStatus.EXPIRED: STATUS_EXPIRED,
}

DEFAULT_MODE_OF_PAYMENT = "Mobile Money"


class PaymentGatewayService:
    def __init__(
        self,
        integrations: IntegrationRepository,
        intents: PaymentIntentRepository,
        events: WebhookEventRepository,
        payments: PaymentRepository,
    ) -> None:
        self.integrations = integrations
        self.intents = intents
        self.events = events
        self.payments = payments

    # -- provider resolution ----------------------------------------------
    def _active_config(self) -> TenantIntegrationConfig:
        config = self.integrations.get_active(KIND_PAYMENT)
        if config is None:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "No mobile-money provider is active. Configure one in Settings.",
            )
        return config

    def _provider_for(self, config: TenantIntegrationConfig) -> PaymentProvider:
        try:
            return build_provider(
                config.provider,
                self.integrations.credentials_for(config),
                mode=config.mode,
            )
        except ProviderConfigError as exc:
            raise HTTPException(http_status.HTTP_409_CONFLICT, str(exc)) from exc

    @staticmethod
    def _new_reference() -> str:
        # Short, unambiguous, and safe to show a customer on a payment prompt.
        return f"EQ{uuid.uuid4().hex[:14].upper()}"

    # -- collections -------------------------------------------------------
    async def create_collection(self, data: CollectionCreate) -> PaymentIntent:
        config = self._active_config()
        provider = self._provider_for(config)

        amount = data.amount
        doctype = "Sales Invoice" if data.invoice_id else ""
        if data.invoice_id:
            summary = await self._settlement_summary(doctype, data.invoice_id)
            if not data.force:
                existing = self._open_intent_for(data.invoice_id)
                if existing is not None:
                    # A second click, or a customer who has not yet confirmed.
                    # Returning the live attempt is the difference between one
                    # prompt and two debits.
                    return existing
            if amount is None:
                amount = int(round(summary["outstanding"]))
        if amount is None or amount <= 0:
            raise HTTPException(
                http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Nothing to collect: specify an amount, or the invoice is settled.",
            )

        msisdn = normalise_msisdn(data.payer_msisdn)
        if not msisdn and not data.hosted:
            raise HTTPException(
                http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                "A payer phone number is required unless you request a payment link.",
            )

        intent = self.intents.add(
            PaymentIntent(
                reference=self._new_reference(),
                direction=DIRECTION_COLLECTION,
                provider=config.provider,
                mode=config.mode,
                amount=amount,
                currency="XAF",
                counterparty_msisdn=msisdn,
                counterparty_name=data.payer_name,
                description=data.description,
                erpnext_doctype=doctype,
                erpnext_docname=data.invoice_id or "",
                status=STATUS_CREATED,
                reconciliation=RECON_PENDING if data.invoice_id else RECON_NOT_APPLICABLE,
            )
        )

        request = CollectionRequest(
            reference=intent.reference,
            amount=amount,
            payer_msisdn=msisdn,
            payer_name=data.payer_name,
            payer_email=data.payer_email,
            description=data.description or f"Invoice {data.invoice_id or ''}".strip(),
            hosted=data.hosted,
            redirect_url=data.redirect_url,
        )
        return await self._initiate(intent, lambda: provider.collect(request))

    # -- payouts -----------------------------------------------------------
    async def create_payout(self, data: PayoutCreate) -> PaymentIntent:
        config = self._active_config()
        provider = self._provider_for(config)

        amount = data.amount
        doctype = "Purchase Invoice" if data.bill_id else ""
        if data.bill_id:
            summary = await self._settlement_summary(doctype, data.bill_id)
            if not data.force:
                existing = self._open_intent_for(data.bill_id)
                if existing is not None:
                    return existing
            if amount is None:
                amount = int(round(summary["outstanding"]))
        if amount is None or amount <= 0:
            raise HTTPException(
                http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Nothing to pay: specify an amount, or the bill is settled.",
            )

        msisdn = normalise_msisdn(data.payee_msisdn)
        if not msisdn:
            raise HTTPException(
                http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                "A payee phone number is required.",
            )

        intent = self.intents.add(
            PaymentIntent(
                reference=self._new_reference(),
                direction=DIRECTION_PAYOUT,
                provider=config.provider,
                mode=config.mode,
                amount=amount,
                currency="XAF",
                counterparty_msisdn=msisdn,
                counterparty_name=data.payee_name,
                description=data.description,
                erpnext_doctype=doctype,
                erpnext_docname=data.bill_id or "",
                status=STATUS_CREATED,
                reconciliation=RECON_PENDING if data.bill_id else RECON_NOT_APPLICABLE,
            )
        )

        request = PayoutRequest(
            reference=intent.reference,
            amount=amount,
            payee_msisdn=msisdn,
            payee_name=data.payee_name,
            payee_email=data.payee_email,
            description=data.description or f"Bill {data.bill_id or ''}".strip(),
        )
        return await self._initiate(intent, lambda: provider.payout(request))

    async def _initiate(self, intent: PaymentIntent, call) -> PaymentIntent:
        try:
            result = await call()
        except PaymentProviderError as exc:
            # The intent row survives the failure on purpose: it is the record
            # that we tried, which matters when a provider actually took the
            # instruction but failed to acknowledge it.
            intent.status = STATUS_FAILED
            intent.failure_reason = str(exc)[:255]
            self.intents.save(intent)
            raise HTTPException(
                http_status.HTTP_502_BAD_GATEWAY
                if exc.retryable
                else http_status.HTTP_400_BAD_REQUEST,
                str(exc),
            ) from exc

        intent.provider_ref = result.provider_ref
        intent.provider_status = result.provider_status
        intent.payment_url = result.payment_url
        intent.ussd_code = result.ussd_code
        intent.operator = result.operator
        intent.status = _STATUS_TO_INTENT.get(result.status, STATUS_PENDING)
        intent.last_payload = json.dumps(result.raw)[:20000]
        return self.intents.save(intent)

    def _open_intent_for(self, docname: str) -> PaymentIntent | None:
        for candidate in self.intents.list(
            erpnext_docname=docname, limit=20
        ):
            if candidate.status in (STATUS_CREATED, STATUS_PENDING):
                return candidate
        return None

    async def _settlement_summary(self, doctype: str, name: str) -> dict:
        try:
            summary = await self.payments.get_settlement_summary(doctype, name)
        except ERPNextError as exc:
            raise HTTPException(
                http_status.HTTP_404_NOT_FOUND,
                f"Could not read {doctype} '{name}': {exc}",
            ) from exc
        if summary.get("docstatus") != 1:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                f"{doctype} '{name}' is not submitted, so it cannot be settled.",
            )
        return summary

    # -- confirmation ------------------------------------------------------
    async def refresh(self, intent: PaymentIntent) -> PaymentIntent:
        """Ask the provider what really happened, then act on the answer."""
        if intent.is_terminal and intent.reconciliation != RECON_PENDING:
            return intent

        if intent.status not in (STATUS_CREATED, STATUS_PENDING):
            # Terminal but unposted — skip the provider call, just try posting.
            return await self._reconcile(intent)

        config = self.integrations.get(intent.provider, KIND_PAYMENT)
        if config is None:
            intent.reconciliation = RECON_NEEDS_REVIEW
            intent.review_reason = (
                f"Provider '{intent.provider}' is no longer configured."
            )
            return self.intents.save(intent)

        provider = self._provider_for(config)
        try:
            result = await provider.get_status(
                intent.provider_ref, direction=intent.direction
            )
        except PaymentProviderError as exc:
            # Unreachable is not failure. Leave it pending for the next sweep;
            # marking it failed here would lose money that is still in flight.
            if exc.retryable:
                return intent
            intent.status = STATUS_FAILED
            intent.failure_reason = str(exc)[:255]
            return self.intents.save(intent)

        return await self._apply_status(intent, result)

    async def _apply_status(
        self, intent: PaymentIntent, result: ProviderStatusResult
    ) -> PaymentIntent:
        intent.provider_status = result.provider_status
        intent.last_payload = json.dumps(result.raw)[:20000]
        if result.operator:
            intent.operator = result.operator
        if result.operator_ref:
            intent.operator_ref = result.operator_ref

        if result.status is PaymentStatus.UNKNOWN:
            # The provider has no record yet — a link nobody opened. Stay put.
            self.intents.save(intent)
            return intent

        intent.status = _STATUS_TO_INTENT.get(result.status, intent.status)
        if result.status is PaymentStatus.FAILED:
            intent.failure_reason = result.failure_reason or "Payment failed"
        self.intents.save(intent)

        if intent.status != STATUS_SUCCEEDED:
            return intent

        # Money moved. Guard the amount before it reaches the ledger.
        if result.amount is not None and int(result.amount) != int(intent.amount):
            intent.reconciliation = RECON_NEEDS_REVIEW
            intent.review_reason = (
                f"Provider settled {result.amount} {result.currency or intent.currency} "
                f"but {intent.amount} was requested."
            )
            return self.intents.mark_confirmed(intent)

        self.intents.mark_confirmed(intent)
        return await self._reconcile(intent)

    async def _reconcile(self, intent: PaymentIntent) -> PaymentIntent:
        """Post a confirmed payment to ERPNext. Safe to call repeatedly."""
        if intent.status != STATUS_SUCCEEDED:
            return intent
        if intent.reconciliation in (RECON_POSTED, RECON_NOT_APPLICABLE):
            return intent
        if intent.reconciliation == RECON_NEEDS_REVIEW:
            return intent
        if not intent.erpnext_docname:
            intent.reconciliation = RECON_NOT_APPLICABLE
            return self.intents.save(intent)

        config = self.integrations.get(intent.provider, KIND_PAYMENT)
        settings = self.integrations.settings_for(config) if config else {}
        mode_of_payment = settings.get("mode_of_payment") or DEFAULT_MODE_OF_PAYMENT

        try:
            payment = await self.payments.record(
                intent.erpnext_doctype,
                intent.erpnext_docname,
                amount=float(intent.amount),
                mode=mode_of_payment,
                posting_date=date.today().isoformat(),
                reference_no=intent.operator_ref or intent.reference,
            )
        except ERPNextError as exc:
            # Distinguish "try again later" from "this will never work".
            message = str(exc)
            if getattr(exc, "status_code", 502) >= 500:
                # ERPNext is down; the sweep will retry. Money is not lost.
                return intent
            intent.reconciliation = RECON_NEEDS_REVIEW
            intent.review_reason = f"Could not post to ERPNext: {message}"[:255]
            return self.intents.save(intent)

        intent.erpnext_payment_entry = payment.id or ""
        intent.reconciliation = RECON_POSTED
        intent.review_reason = ""
        return self.intents.save(intent)

    # -- webhooks ----------------------------------------------------------
    async def handle_webhook(
        self, provider_name: str, headers: dict[str, str], raw_body: bytes
    ) -> None:
        """Record a callback, then confirm it out-of-band.

        Never raises to the caller: a provider that receives an error will
        retry, and a retry storm helps nobody. Everything is recorded instead.
        """
        config = self.integrations.get(provider_name, KIND_PAYMENT)
        if config is None:
            return

        try:
            provider = build_provider(
                provider_name,
                self.integrations.credentials_for(config),
                mode=config.mode,
            )
        except ProviderConfigError:
            return

        hint: WebhookHint = provider.parse_webhook(
            headers, raw_body, self.integrations.webhook_secret_for(config)
        )
        event_key = hint.event_key or hint.our_reference
        if not event_key:
            return

        event = self.events.claim(
            provider_name, event_key, raw_body.decode("utf-8", "replace")
        )
        if event is None:
            # Already handled. Providers retry; that is normal, not an error.
            return

        intent = self.intents.find_for_webhook(
            provider_name, hint.provider_ref, hint.our_reference
        )
        if intent is None:
            self.events.record_outcome(
                event, OUTCOME_UNKNOWN_INTENT, f"No intent for {event_key}"
            )
            return

        try:
            # The callback is only a nudge — refresh() re-asks the provider.
            await self.refresh(intent)
        except Exception as exc:  # noqa: BLE001 - never surface to the provider
            self.events.record_outcome(event, OUTCOME_ERROR, str(exc))

    # -- sweep -------------------------------------------------------------
    async def sweep(self, limit: int = 200) -> SweepResult:
        """Poll everything in flight and retry everything unposted.

        The backstop for callbacks that never arrive, which is a routine
        occurrence rather than an exceptional one.
        """
        checked = settled = posted = review = pending = 0
        errors: list[str] = []

        for intent in self.intents.list_open(limit=limit):
            checked += 1
            try:
                updated = await self.refresh(intent)
            except Exception as exc:  # noqa: BLE001 - one bad intent must not stop the sweep
                errors.append(f"{intent.reference}: {exc}")
                continue
            if updated.status == STATUS_SUCCEEDED:
                settled += 1
            elif updated.status in (STATUS_CREATED, STATUS_PENDING):
                pending += 1

        for intent in self.intents.list_unposted(limit=limit):
            try:
                updated = await self._reconcile(intent)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{intent.reference}: {exc}")
                continue
            if updated.reconciliation == RECON_POSTED:
                posted += 1
            elif updated.reconciliation == RECON_NEEDS_REVIEW:
                review += 1

        return SweepResult(
            checked=checked,
            settled=settled,
            posted=posted,
            needs_review=review,
            still_pending=pending,
            errors=errors[:20],
        )

    # -- manual intervention ----------------------------------------------
    async def retry_posting(self, intent_id: int) -> PaymentIntent:
        """Clear a review flag and try posting again (after a human fixed it)."""
        intent = self.intents.get(intent_id)
        if intent is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Payment not found")
        if intent.status != STATUS_SUCCEEDED:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "Only a confirmed payment can be posted.",
            )
        intent.reconciliation = RECON_PENDING
        intent.review_reason = ""
        self.intents.save(intent)
        return await self._reconcile(intent)

    def attach_document(
        self, intent_id: int, doctype: str, docname: str
    ) -> PaymentIntent:
        """Point an orphaned payment at the invoice it belongs to.

        The manual half of reconciliation: someone paid without a reference, or
        against the wrong one, and a human has worked out which invoice it was.
        """
        intent = self.intents.get(intent_id)
        if intent is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Payment not found")
        if intent.reconciliation == RECON_POSTED:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "This payment is already posted to the ledger.",
            )
        intent.erpnext_doctype = doctype
        intent.erpnext_docname = docname
        intent.reconciliation = RECON_PENDING
        intent.review_reason = ""
        return self.intents.save(intent)
