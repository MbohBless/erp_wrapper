"""Fapshi — MTN MoMo, Orange Money and Fapshi-wallet collection/payout.

Endpoints per docs.fapshi.com:

    POST /initiate-pay            hosted checkout link (expires after 24h)
    POST /direct-pay              handset prompt; never expires
    GET  /payment-status/{id}     status (max 6 requests/min per transaction)
    POST /expire-pay              invalidate a link
    POST /payout                  send money out
    GET  /balance

Base URL: https://sandbox.fapshi.com | https://live.fapshi.com
Auth: ``apiuser`` and ``apikey`` request headers (not a bearer token).

**Collections and payouts need separate credentials.** Fapshi disables
collection on a service once payouts are enabled for it, so a tenant that does
both holds two services. Credentials are therefore stored as::

    {"apiuser": ..., "apikey": ...,
     "payout_apiuser": ..., "payout_apikey": ...}

falling back to the collection pair when the payout pair is absent — which is
correct for a tenant that only ever collects.
"""

import json
import secrets
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
    local_msisdn,
)

_SANDBOX = "https://sandbox.fapshi.com"
_LIVE = "https://live.fapshi.com"

# Fapshi rejects anything under 100 XAF.
MIN_AMOUNT_XAF = 100

_STATUS_MAP = {
    "CREATED": PaymentStatus.PENDING,
    "PENDING": PaymentStatus.PENDING,
    "SUCCESSFUL": PaymentStatus.SUCCEEDED,
    "FAILED": PaymentStatus.FAILED,
    "EXPIRED": PaymentStatus.EXPIRED,
}

# "mobile money" is MTN; "orange money" is Orange. Omitting it lets Fapshi
# detect the operator from the number, which is what we want by default.
MEDIUM_MTN = "mobile money"
MEDIUM_ORANGE = "orange money"


class FapshiProvider:
    name = "fapshi"
    # Fapshi signs callbacks with a shared secret in the `x-wh-secret` header,
    # configured in the merchant dashboard.
    supports_webhook_verification = True

    def __init__(
        self,
        credentials: dict[str, Any],
        *,
        mode: str = "sandbox",
        timeout: float = 30.0,
    ) -> None:
        self.mode = mode
        self.base_url = _SANDBOX if mode != "live" else _LIVE
        self._apiuser = str(credentials.get("apiuser") or "")
        self._apikey = str(credentials.get("apikey") or "")
        # Separate payout service; falls back to the collection pair.
        self._payout_apiuser = str(credentials.get("payout_apiuser") or self._apiuser)
        self._payout_apikey = str(credentials.get("payout_apikey") or self._apikey)
        self._timeout = timeout

        if not self._apiuser or not self._apikey:
            raise ProviderConfigError(
                "Fapshi needs apiuser and apikey from your service's API keys."
            )

    # -- transport ---------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        payout: bool = False,
    ) -> dict:
        headers = {
            "Accept": "application/json",
            "apiuser": self._payout_apiuser if payout else self._apiuser,
            "apikey": self._payout_apikey if payout else self._apikey,
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    # Fapshi rejects GETs that carry a body.
                    json=json_body if json_body is not None else None,
                )
        except httpx.RequestError as exc:
            raise ProviderUnavailable(f"Fapshi is unreachable: {exc}") from exc

        if resp.status_code == 429:
            raise ProviderUnavailable(
                "Fapshi rate limit reached (max 6 status checks per minute per "
                "transaction)."
            )
        if resp.status_code >= 500:
            raise ProviderUnavailable(f"Fapshi error {resp.status_code}: {resp.text}")
        try:
            body = resp.json()
        except ValueError:
            raise PaymentProviderError(
                f"Fapshi returned a non-JSON response ({resp.status_code})"
            ) from None
        if resp.status_code >= 400:
            raise PaymentProviderError(
                f"Fapshi rejected the request: {body.get('message') or resp.text}"
            )
        return body if isinstance(body, dict) else {}

    @staticmethod
    def _check_amount(amount: int) -> None:
        if amount < MIN_AMOUNT_XAF:
            raise PaymentProviderError(
                f"Fapshi requires at least {MIN_AMOUNT_XAF} XAF; got {amount}."
            )

    # -- operations --------------------------------------------------------
    async def collect(self, request: CollectionRequest) -> ProviderIntent:
        self._check_amount(request.amount)
        payload: dict[str, Any] = {
            "amount": request.amount,
            "externalId": request.reference,
            "message": request.description or f"Payment {request.reference}",
        }
        if request.payer_email:
            payload["email"] = request.payer_email

        if request.hosted or not request.payer_msisdn:
            # No number to prompt, or explicitly asked for a link.
            if request.redirect_url:
                payload["redirectUrl"] = request.redirect_url
            body = await self._request("POST", "/initiate-pay", json_body=payload)
            return ProviderIntent(
                provider_ref=str(body.get("transId") or ""),
                status=PaymentStatus.PENDING,
                payment_url=str(body.get("link") or ""),
                raw=body,
            )

        payload["phone"] = local_msisdn(request.payer_msisdn)
        if request.payer_name:
            payload["name"] = request.payer_name
        body = await self._request("POST", "/direct-pay", json_body=payload)
        return ProviderIntent(
            provider_ref=str(body.get("transId") or ""),
            status=PaymentStatus.PENDING,
            raw=body,
        )

    async def payout(self, request: PayoutRequest) -> ProviderIntent:
        self._check_amount(request.amount)
        payload: dict[str, Any] = {
            "amount": request.amount,
            "phone": local_msisdn(request.payee_msisdn),
            "externalId": request.reference,
            "message": request.description or f"Payout {request.reference}",
        }
        if request.payee_name:
            payload["name"] = request.payee_name
        if request.payee_email:
            payload["email"] = request.payee_email
        body = await self._request("POST", "/payout", json_body=payload, payout=True)
        return ProviderIntent(
            provider_ref=str(body.get("transId") or ""),
            status=PaymentStatus.PENDING,
            raw=body,
        )

    async def get_status(
        self, provider_ref: str, *, direction: str = "collection"
    ) -> ProviderStatusResult:
        if not provider_ref:
            return ProviderStatusResult(provider_ref="", status=PaymentStatus.UNKNOWN)
        body = await self._request(
            "GET",
            f"/payment-status/{provider_ref}",
            payout=(direction == "payout"),
        )
        raw_status = str(body.get("status") or "")
        amount = body.get("amount")
        return ProviderStatusResult(
            provider_ref=str(body.get("transId") or provider_ref),
            status=_STATUS_MAP.get(raw_status, PaymentStatus.UNKNOWN),
            provider_status=raw_status,
            amount=int(amount) if isinstance(amount, (int, float)) else None,
            currency="XAF",
            operator=str(body.get("medium") or ""),
            operator_ref=str(body.get("financialTransId") or ""),
            failure_reason=str(body.get("reason") or ""),
            raw=body,
        )

    async def expire(self, provider_ref: str) -> dict:
        """Invalidate a checkout link early (e.g. the invoice was cancelled)."""
        return await self._request(
            "POST", "/expire-pay", json_body={"transId": provider_ref}
        )

    async def get_balance(self) -> dict:
        return await self._request("GET", "/balance")

    # -- webhook -----------------------------------------------------------
    def parse_webhook(
        self, headers: dict[str, str], raw_body: bytes, webhook_secret: str
    ) -> WebhookHint:
        try:
            body = json.loads(raw_body or b"{}")
        except ValueError:
            return WebhookHint(event_key="", verified=False)
        if not isinstance(body, dict):
            return WebhookHint(event_key="", verified=False)

        # Header names arrive with inconsistent casing across proxies.
        supplied = ""
        for key, value in headers.items():
            if key.lower() == "x-wh-secret":
                supplied = value or ""
                break
        verified = bool(
            webhook_secret and secrets.compare_digest(supplied, webhook_secret)
        )

        trans_id = str(body.get("transId") or "")
        return WebhookHint(
            event_key=trans_id,
            provider_ref=trans_id,
            our_reference=str(body.get("externalId") or ""),
            claimed_status=str(body.get("status") or ""),
            verified=verified,
            raw=body,
        )
