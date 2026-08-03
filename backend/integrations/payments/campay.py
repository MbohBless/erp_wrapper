"""CamPay (TAKWID GROUP) — MTN MoMo and Orange Money collection/disbursement.

Endpoints verified against the official Python SDK
(github.com/CamPay/campay-python-sdk, ``src/campay/sdk.py``) because CamPay's
reference docs are a Postman collection that cannot be read programmatically:

    POST /api/token/                  {username, password} -> {token}
    POST /api/collect/                request money from a payer
    POST /api/withdraw/               send money to a payee
    POST /api/get_payment_link/       hosted checkout
    GET  /api/transaction/{ref}/      status
    GET  /api/balance/

Base URL: https://demo.campay.net (sandbox) | https://www.campay.net (live).

Two deliberate departures from CamPay's own SDK:

* **TLS verification stays on.** Their SDK passes ``verify=False`` on every
  call, which silently accepts any certificate — an interceptable channel
  carrying payment instructions. We verify.
* **Tokens are cached.** Their SDK fetches a fresh token before every single
  request; we reuse one until it is near expiry.

Credentials: ``{"app_username": ..., "app_password": ...}``.
"""

import json
import time
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

_SANDBOX = "https://demo.campay.net"
_LIVE = "https://www.campay.net"

# CamPay tokens are long-lived; refresh a minute early rather than racing expiry.
_TOKEN_SKEW_SECONDS = 60

_STATUS_MAP = {
    "SUCCESSFUL": PaymentStatus.SUCCEEDED,
    "FAILED": PaymentStatus.FAILED,
    "PENDING": PaymentStatus.PENDING,
}


class CamPayProvider:
    name = "campay"
    # CamPay posts a signed payload, but the signing scheme is documented only
    # inside the merchant dashboard. We treat callbacks as unverified hints and
    # confirm every one through the status endpoint, which is safe either way.
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
        self._username = str(credentials.get("app_username") or "")
        self._password = str(credentials.get("app_password") or "")
        self._timeout = timeout
        self._token: str | None = None
        self._token_expires_at: float = 0.0

        if not self._username or not self._password:
            raise ProviderConfigError(
                "CamPay needs app_username and app_password from your app's "
                "APP KEYS section."
            )

    # -- transport ---------------------------------------------------------
    async def _request(
        self, method: str, path: str, *, json_body: dict | None = None, auth: bool = True
    ) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"Token {await self._get_token()}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(
                    method, f"{self.base_url}{path}", headers=headers, json=json_body
                )
        except httpx.RequestError as exc:
            raise ProviderUnavailable(f"CamPay is unreachable: {exc}") from exc

        if resp.status_code >= 500:
            raise ProviderUnavailable(f"CamPay error {resp.status_code}: {resp.text}")
        try:
            body = resp.json()
        except ValueError:
            raise PaymentProviderError(
                f"CamPay returned a non-JSON response ({resp.status_code})"
            ) from None
        if resp.status_code >= 400:
            detail = body.get("message") or body.get("detail") or resp.text
            raise PaymentProviderError(f"CamPay rejected the request: {detail}")
        return body

    async def _get_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        body = await self._request(
            "POST",
            "/api/token/",
            json_body={"username": self._username, "password": self._password},
            auth=False,
        )
        token = body.get("token")
        if not token:
            raise ProviderConfigError("CamPay did not return a token; check credentials.")
        self._token = str(token)
        # CamPay does not report a TTL on this endpoint; assume a conservative
        # hour so a stale token cannot wedge collections for long.
        self._token_expires_at = time.monotonic() + 3600 - _TOKEN_SKEW_SECONDS
        return self._token

    # -- operations --------------------------------------------------------
    async def collect(self, request: CollectionRequest) -> ProviderIntent:
        if request.hosted:
            return await self._payment_link(request)

        payload = {
            "amount": str(request.amount),
            "currency": request.currency,
            "from": normalise_msisdn(request.payer_msisdn),
            "description": request.description or f"Payment {request.reference}",
            "external_reference": request.reference,
        }
        body = await self._request("POST", "/api/collect/", json_body=payload)
        return ProviderIntent(
            provider_ref=str(body.get("reference") or ""),
            # /api/collect/ returns before the payer has approved on their
            # handset, so this is always pending regardless of what it says.
            status=PaymentStatus.PENDING,
            provider_status=str(body.get("status") or "PENDING"),
            ussd_code=str(body.get("ussd_code") or ""),
            operator=str(body.get("operator") or ""),
            raw=body,
        )

    async def _payment_link(self, request: CollectionRequest) -> ProviderIntent:
        payload = {
            "amount": str(request.amount),
            "currency": request.currency,
            "description": request.description or f"Payment {request.reference}",
            "external_reference": request.reference,
            "redirect_url": request.redirect_url,
            "failure_redirect_url": request.failure_redirect_url,
            "payment_options": "MOMO",
        }
        if request.payer_msisdn:
            payload["from"] = normalise_msisdn(request.payer_msisdn)
        if request.payer_email:
            payload["email"] = request.payer_email
        if request.payer_name:
            first, _, last = request.payer_name.partition(" ")
            payload["first_name"] = first
            payload["last_name"] = last

        body = await self._request("POST", "/api/get_payment_link/", json_body=payload)
        return ProviderIntent(
            provider_ref=str(body.get("reference") or ""),
            status=PaymentStatus.PENDING,
            provider_status=str(body.get("status") or ""),
            payment_url=str(body.get("link") or ""),
            raw=body,
        )

    async def payout(self, request: PayoutRequest) -> ProviderIntent:
        payload = {
            "amount": str(request.amount),
            "currency": request.currency,
            "to": normalise_msisdn(request.payee_msisdn),
            "description": request.description or f"Payout {request.reference}",
            "external_reference": request.reference,
        }
        body = await self._request("POST", "/api/withdraw/", json_body=payload)
        return ProviderIntent(
            provider_ref=str(body.get("reference") or ""),
            status=_STATUS_MAP.get(str(body.get("status") or ""), PaymentStatus.PENDING),
            provider_status=str(body.get("status") or ""),
            operator=str(body.get("operator") or ""),
            raw=body,
        )

    async def get_status(
        self, provider_ref: str, *, direction: str = "collection"  # noqa: ARG002
    ) -> ProviderStatusResult:
        if not provider_ref:
            return ProviderStatusResult(provider_ref="", status=PaymentStatus.UNKNOWN)
        try:
            body = await self._request("GET", f"/api/transaction/{provider_ref}/")
        except PaymentProviderError as exc:
            # A payment link nobody has opened has no transaction yet. That is
            # "not started", not "failed" — cancelling it would kill live links.
            if "not found" in str(exc).lower():
                return ProviderStatusResult(
                    provider_ref=provider_ref, status=PaymentStatus.UNKNOWN
                )
            raise

        raw_status = str(body.get("status") or "")
        amount = body.get("amount")
        return ProviderStatusResult(
            provider_ref=str(body.get("reference") or provider_ref),
            status=_STATUS_MAP.get(raw_status, PaymentStatus.UNKNOWN),
            provider_status=raw_status,
            amount=int(float(amount)) if amount is not None else None,
            currency=str(body.get("currency") or ""),
            operator=str(body.get("operator") or ""),
            operator_ref=str(body.get("operator_reference") or ""),
            failure_reason=str(body.get("reason") or ""),
            raw=body,
        )

    async def get_balance(self) -> dict:
        return await self._request("GET", "/api/balance/")

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

        reference = str(body.get("reference") or "")
        return WebhookHint(
            event_key=reference or str(body.get("external_reference") or ""),
            provider_ref=reference,
            our_reference=str(body.get("external_reference") or ""),
            claimed_status=str(body.get("status") or ""),
            verified=False,  # confirmed via get_status() before anything is posted
            raw=body,
        )
