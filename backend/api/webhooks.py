"""Inbound provider callbacks.

Unauthenticated by necessity — a payment provider cannot carry a user session —
but **not** unprotected:

* the route is still behind ``TenantMiddleware``, so the callback URL is
  per-tenant (``https://<tenant>.equimed.app/api/webhooks/payments/<provider>``)
  and an unknown host is refused before any handler runs;
* nothing here is trusted. The payload identifies a transaction and nothing
  more; the service re-confirms status directly with the provider before a
  single line reaches the ledger;
* every delivery is recorded and deduplicated, so a replayed callback cannot
  post a payment twice.

**Always answers 200.** Providers retry on any non-2xx, and a retry storm
caused by our own bug helps nobody — failures are recorded, not signalled. The
body is deliberately uninformative so a prober learns nothing about which
references exist.

A suspended tenant's callbacks are rejected upstream by the middleware. That is
intentional: their ledger should not be written to. The payment is not lost —
the provider remains authoritative and ``POST /gateway/sweep`` picks it up once
the workspace is restored.
"""

from fastapi import APIRouter, Depends, Request

from api.deps import get_payment_gateway_service
from schemas.gateway import WebhookAck
from services.payment_gateway_service import PaymentGatewayService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/payments/{provider}", response_model=WebhookAck)
async def payment_webhook(
    provider: str,
    request: Request,
    service: PaymentGatewayService = Depends(get_payment_gateway_service),
) -> WebhookAck:
    # Raw bytes, not the parsed body: signature schemes are computed over the
    # exact payload, and re-serialising it would break verification.
    raw_body = await request.body()
    headers = {key: value for key, value in request.headers.items()}
    await service.handle_webhook(provider, headers, raw_body)
    return WebhookAck()
