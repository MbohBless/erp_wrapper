"""MTN Mobile Money — direct integration against MTN's Open API.

Worth having alongside the aggregators: MTN is the largest wallet in Cameroon
and going direct removes the aggregator's 1–2 point spread once volume makes
the extra operational work worthwhile.

Endpoints (momodeveloper.mtn.com):

    POST /collection/token/                    Basic auth -> bearer token
    POST /collection/v1_0/requesttopay         request money (202, empty body)
    GET  /collection/v1_0/requesttopay/{ref}   status
    GET  /collection/v1_0/account/balance
    POST /disbursement/token/
    POST /disbursement/v1_0/transfer           send money (202, empty body)
    GET  /disbursement/v1_0/transfer/{ref}     status

Base URL: https://sandbox.momodeveloper.mtn.com | https://proxy.momoapi.mtn.com

Three things make MTN different from the aggregators:

* **We generate the transaction id.** ``X-Reference-Id`` is a UUID we choose,
  and it is both the idempotency key and the handle for later status queries.
  Re-sending the same UUID cannot create a second charge.
* **Collections and disbursements are separate products** with separate
  subscription keys and separate tokens.
* **Callbacks are unauthenticated.** MTN POSTs to ``X-Callback-Url`` with no
  signature at all, so a callback can only ever be a hint to go and check.

Credentials::

    {"api_user": "<uuid>", "api_key": "...",
     "collection_subscription_key": "...",
     "disbursement_subscription_key": "...",   # optional, payouts only
     "target_environment": "mtncameroon"}      # "sandbox" in sandbox
"""

import base64
import json
import time
import uuid
from typing import Any

import httpx

from integrations.payments.base import (
    CollectionRequest,
    PayoutRequest,
    PaymentProviderError,
    PaymentStatus,
    ProviderConfigError,
    ProviderIntent,
    ProviderStatusResult,
    ProviderUnavailable,
    WebhookHint,
    normalise_msisdn,
)

_SANDBOX = "https://sandbox.momodeveloper.mtn.com"
_LIVE = "https://proxy.momoapi.mtn.com"

_TOKEN_SKEW_SECONDS = 60

_STATUS_MAP = {
    "SUCCESSFUL": PaymentStatus.SUCCEEDED,
    "FAILED": PaymentStatus.FAILED,
    "PENDING": PaymentStatus.PENDING,
    "TIMEOUT": PaymentStatus.FAILED,
}

_COLLECTION = "collection"
_DISBURSEMENT = "disbursement"


class MtnMomoProvider:
    name = "mtn_momo"
    # MTN sends no signature or shared secret with its callbacks.
    supports_webhook_verification = False

    def __init__(
        self,
        credentials: dict[str, Any],
        *,
        mode: str = "sandbox",
        timeout: float = 30.0,
    ) -> None:
        self.mode = mode
        self.base_url = _SANDBOX if mode != "live" else _LIVE
        self._api_user = str(credentials.get("api_user") or "")
        self._api_key = str(credentials.get("api_key") or "")
        self._keys = {
            _COLLECTION: str(credentials.get("collection_subscription_key") or ""),
            _DISBURSEMENT: str(credentials.get("disbursement_subscription_key") or ""),
        }
        self._target_environment = str(
            credentials.get("target_environment")
            or ("sandbox" if mode != "live" else "mtncameroon")
        )
        self._timeout = timeout
        self._tokens: dict[str, tuple[str, float]] = {}

        if not self._api_user or not self._api_key:
            raise ProviderConfigError("MTN MoMo needs api_user and api_key.")
        if not self._keys[_COLLECTION]:
            raise ProviderConfigError(
                "MTN MoMo needs collection_subscription_key (Collections product)."
            )

    def _subscription_key(self, product: str) -> str:
        key = self._keys.get(product) or ""
        if not key:
            raise ProviderConfigError(
                f"MTN MoMo {product} is not configured; add its subscription key."
            )
        return key

    # -- transport ---------------------------------------------------------
    async def _token(self, product: str) -> str:
        cached = self._tokens.get(product)
        if cached and time.monotonic() < cached[1]:
            return cached[0]

        basic = base64.b64encode(
            f"{self._api_user}:{self._api_key}".encode("utf-8")
        ).decode("ascii")
        headers = {
            "Authorization": f"Basic {basic}",
            "Ocp-Apim-Subscription-Key": self._subscription_key(product),
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/{product}/token/", headers=headers
                )
        except httpx.RequestError as exc:
            raise ProviderUnavailable(f"MTN MoMo is unreachable: {exc}") from exc

        if resp.status_code >= 500:
            raise ProviderUnavailable(f"MTN MoMo error {resp.status_code}")
        if resp.status_code >= 400:
            raise ProviderConfigError(
                f"MTN MoMo rejected the credentials ({resp.status_code}). Check "
                "api_user, api_key and the subscription key."
            )
        body = resp.json()
        token = str(body.get("access_token") or "")
        if not token:
            raise ProviderConfigError("MTN MoMo returned no access_token.")
        ttl = int(body.get("expires_in") or 3600)
        self._tokens[product] = (token, time.monotonic() + ttl - _TOKEN_SKEW_SECONDS)
        return token

    async def _headers(self, product: str, *, reference: str = "") -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {await self._token(product)}",
            "Ocp-Apim-Subscription-Key": self._subscription_key(product),
            "X-Target-Environment": self._target_environment,
            "Content-Type": "application/json",
        }
        if reference:
            headers["X-Reference-Id"] = reference
        return headers

    # -- operations --------------------------------------------------------
    @staticmethod
    def _transaction_id(reference: str) -> str:
        """MTN requires a UUID. Derive one deterministically from our reference
        so a retry of the same logical payment reuses the same id and cannot
        double-charge."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"equimed:payment:{reference}"))

    async def collect(self, request: CollectionRequest) -> ProviderIntent:
        transaction_id = self._transaction_id(request.reference)
        payload = {
            "amount": str(request.amount),
            "currency": request.currency,
            "externalId": request.reference,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": normalise_msisdn(request.payer_msisdn),
            },
            "payerMessage": (request.description or "Payment")[:160],
            "payeeNote": request.reference[:160],
        }
        await self._submit(
            _COLLECTION, "/collection/v1_0/requesttopay", transaction_id, payload
        )
        return ProviderIntent(
            provider_ref=transaction_id,
            status=PaymentStatus.PENDING,
            operator="MTN",
            raw={"transaction_id": transaction_id},
        )

    async def payout(self, request: PayoutRequest) -> ProviderIntent:
        transaction_id = self._transaction_id(request.reference)
        payload = {
            "amount": str(request.amount),
            "currency": request.currency,
            "externalId": request.reference,
            "payee": {
                "partyIdType": "MSISDN",
                "partyId": normalise_msisdn(request.payee_msisdn),
            },
            "payerMessage": (request.description or "Payout")[:160],
            "payeeNote": request.reference[:160],
        }
        await self._submit(
            _DISBURSEMENT, "/disbursement/v1_0/transfer", transaction_id, payload
        )
        return ProviderIntent(
            provider_ref=transaction_id,
            status=PaymentStatus.PENDING,
            operator="MTN",
            raw={"transaction_id": transaction_id},
        )

    async def _submit(
        self, product: str, path: str, transaction_id: str, payload: dict
    ) -> None:
        headers = await self._headers(product, reference=transaction_id)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self.base_url}{path}", headers=headers, json=payload
                )
        except httpx.RequestError as exc:
            raise ProviderUnavailable(f"MTN MoMo is unreachable: {exc}") from exc

        # 202 Accepted with an empty body is the success case.
        if resp.status_code == 202:
            return
        # Replaying the same X-Reference-Id is how we retry safely; MTN reports
        # it as a conflict, which for us means "already submitted".
        if resp.status_code == 409:
            return
        if resp.status_code >= 500:
            raise ProviderUnavailable(f"MTN MoMo error {resp.status_code}: {resp.text}")
        raise PaymentProviderError(
            f"MTN MoMo rejected the request ({resp.status_code}): {resp.text}"
        )

    async def get_status(
        self, provider_ref: str, *, direction: str = "collection"
    ) -> ProviderStatusResult:
        if not provider_ref:
            return ProviderStatusResult(provider_ref="", status=PaymentStatus.UNKNOWN)

        if direction == "payout":
            product, path = _DISBURSEMENT, f"/disbursement/v1_0/transfer/{provider_ref}"
        else:
            product, path = _COLLECTION, f"/collection/v1_0/requesttopay/{provider_ref}"

        headers = await self._headers(product)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(f"{self.base_url}{path}", headers=headers)
        except httpx.RequestError as exc:
            raise ProviderUnavailable(f"MTN MoMo is unreachable: {exc}") from exc

        if resp.status_code == 404:
            return ProviderStatusResult(
                provider_ref=provider_ref, status=PaymentStatus.UNKNOWN
            )
        if resp.status_code >= 500:
            raise ProviderUnavailable(f"MTN MoMo error {resp.status_code}")
        if resp.status_code >= 400:
            raise PaymentProviderError(
                f"MTN MoMo status check failed ({resp.status_code}): {resp.text}"
            )

        body = resp.json()
        raw_status = str(body.get("status") or "")
        amount = body.get("amount")
        return ProviderStatusResult(
            provider_ref=provider_ref,
            status=_STATUS_MAP.get(raw_status, PaymentStatus.UNKNOWN),
            provider_status=raw_status,
            amount=int(float(amount)) if amount not in (None, "") else None,
            currency=str(body.get("currency") or ""),
            operator="MTN",
            operator_ref=str(body.get("financialTransactionId") or ""),
            failure_reason=str(body.get("reason") or ""),
            raw=body,
        )

    async def get_balance(self) -> dict:
        headers = await self._headers(_COLLECTION)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self.base_url}/collection/v1_0/account/balance", headers=headers
            )
        return resp.json() if resp.status_code < 400 else {}

    # -- webhook -----------------------------------------------------------
    def parse_webhook(
        self, headers: dict[str, str], raw_body: bytes, webhook_secret: str  # noqa: ARG002
    ) -> WebhookHint:
        try:
            body = json.loads(raw_body or b"{}")
        except ValueError:
            return WebhookHint(event_key="", verified=False)
        if not isinstance(body, dict):
            return WebhookHint(event_key="", verified=False)

        # MTN echoes our externalId; the reference id may arrive in a header.
        reference_id = str(body.get("referenceId") or "")
        for key, value in headers.items():
            if key.lower() == "x-reference-id" and value:
                reference_id = value
                break
        external_id = str(body.get("externalId") or "")
        return WebhookHint(
            event_key=reference_id or external_id,
            provider_ref=reference_id,
            our_reference=external_id,
            claimed_status=str(body.get("status") or ""),
            verified=False,  # MTN signs nothing; status is always re-confirmed
            raw=body,
        )
