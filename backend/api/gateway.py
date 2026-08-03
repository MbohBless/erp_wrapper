"""Mobile-money gateway endpoints.

Gated on the ``mobile_money`` plan feature as well as role, so the capability
can be sold per plan (see docs/multi-tenancy.md).

Access (Administrator always allowed):
  - provider configuration: Manager only — these credentials move real money
  - request/send payments: Manager, Accountant
  - read: Manager, Accountant, Sales (Sales needs to chase an unpaid invoice)
"""

from fastapi import APIRouter, Depends, Query, status

from api.deps import (
    get_integration_service,
    get_payment_gateway_service,
    require_feature,
    require_roles,
)
from models.user import Role
from schemas.gateway import (
    CollectionCreate,
    PaymentIntentRead,
    PayoutCreate,
    ProviderCatalogEntry,
    ProviderConfigRead,
    ProviderConfigUpsert,
    SweepResult,
)
from services.integration_service import IntegrationService
from services.payment_gateway_service import PaymentGatewayService

router = APIRouter(prefix="/gateway", tags=["gateway"])

has_gateway = require_feature("mobile_money")
can_configure = require_roles(Role.MANAGER)
can_transact = require_roles(Role.MANAGER, Role.ACCOUNTANT)
can_view = require_roles(Role.MANAGER, Role.ACCOUNTANT, Role.SALES)


# --- Provider configuration ----------------------------------------------
@router.get(
    "/providers/catalog",
    response_model=list[ProviderCatalogEntry],
    dependencies=[Depends(can_configure), Depends(has_gateway)],
)
def provider_catalog(
    service: IntegrationService = Depends(get_integration_service),
) -> list[ProviderCatalogEntry]:
    """Which providers exist and what each needs configured."""
    return service.catalog()


@router.get(
    "/providers",
    response_model=list[ProviderConfigRead],
    dependencies=[Depends(can_configure), Depends(has_gateway)],
)
def list_providers(
    service: IntegrationService = Depends(get_integration_service),
) -> list[ProviderConfigRead]:
    return service.list()


@router.put(
    "/providers",
    response_model=ProviderConfigRead,
    dependencies=[Depends(can_configure), Depends(has_gateway)],
)
def upsert_provider(
    data: ProviderConfigUpsert,
    service: IntegrationService = Depends(get_integration_service),
) -> ProviderConfigRead:
    """Save credentials. Omit `credentials` to edit other fields without
    re-entering secrets; the response never echoes them back."""
    return service.upsert(data)


@router.post(
    "/providers/{provider}/activate",
    response_model=ProviderConfigRead,
    dependencies=[Depends(can_configure), Depends(has_gateway)],
)
def activate_provider(
    provider: str,
    service: IntegrationService = Depends(get_integration_service),
) -> ProviderConfigRead:
    """Route this tenant's payments through `provider`, deactivating the rest."""
    return service.activate(provider)


@router.post(
    "/providers/deactivate",
    response_model=list[ProviderConfigRead],
    dependencies=[Depends(can_configure), Depends(has_gateway)],
)
def deactivate_providers(
    service: IntegrationService = Depends(get_integration_service),
) -> list[ProviderConfigRead]:
    """Stop accepting mobile money entirely — the tenant's own kill switch."""
    return service.deactivate_all()


@router.delete(
    "/providers/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(can_configure), Depends(has_gateway)],
)
def delete_provider(
    provider: str,
    service: IntegrationService = Depends(get_integration_service),
) -> None:
    service.delete(provider)


# --- Collections and payouts ----------------------------------------------
@router.post(
    "/collections",
    response_model=PaymentIntentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_transact), Depends(has_gateway)],
)
async def create_collection(
    data: CollectionCreate,
    service: PaymentGatewayService = Depends(get_payment_gateway_service),
) -> PaymentIntentRead:
    """Ask a customer to pay. Returns as soon as the request is accepted — the
    payment is not confirmed until the provider says so."""
    return PaymentIntentRead.model_validate(await service.create_collection(data))


@router.post(
    "/payouts",
    response_model=PaymentIntentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_transact), Depends(has_gateway)],
)
async def create_payout(
    data: PayoutCreate,
    service: PaymentGatewayService = Depends(get_payment_gateway_service),
) -> PaymentIntentRead:
    """Send money out to settle a supplier bill."""
    return PaymentIntentRead.model_validate(await service.create_payout(data))


@router.get(
    "/payments",
    response_model=list[PaymentIntentRead],
    dependencies=[Depends(can_view), Depends(has_gateway)],
)
def list_payments(
    direction: str | None = None,
    payment_status: str | None = Query(default=None, alias="status"),
    reconciliation: str | None = None,
    invoice_id: str | None = None,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    service: PaymentGatewayService = Depends(get_payment_gateway_service),
) -> list[PaymentIntentRead]:
    rows = service.intents.list(
        direction=direction,
        status=payment_status,
        reconciliation=reconciliation,
        erpnext_docname=invoice_id,
        skip=skip,
        limit=limit,
    )
    return [PaymentIntentRead.model_validate(r) for r in rows]


@router.get(
    "/payments/{intent_id}",
    response_model=PaymentIntentRead,
    dependencies=[Depends(can_view), Depends(has_gateway)],
)
async def get_payment(
    intent_id: int,
    refresh: bool = Query(default=False, description="Re-check with the provider"),
    service: PaymentGatewayService = Depends(get_payment_gateway_service),
) -> PaymentIntentRead:
    from fastapi import HTTPException

    intent = service.intents.get(intent_id)
    if intent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    if refresh:
        intent = await service.refresh(intent)
    return PaymentIntentRead.model_validate(intent)


# --- Reconciliation -------------------------------------------------------
@router.post(
    "/sweep",
    response_model=SweepResult,
    dependencies=[Depends(can_transact), Depends(has_gateway)],
)
async def sweep(
    service: PaymentGatewayService = Depends(get_payment_gateway_service),
) -> SweepResult:
    """Poll every in-flight payment and retry every unposted one.

    The backstop for callbacks that never arrive. Safe to run on a schedule.
    """
    return await service.sweep()


@router.post(
    "/payments/{intent_id}/retry-posting",
    response_model=PaymentIntentRead,
    dependencies=[Depends(can_transact), Depends(has_gateway)],
)
async def retry_posting(
    intent_id: int,
    service: PaymentGatewayService = Depends(get_payment_gateway_service),
) -> PaymentIntentRead:
    """Post a confirmed payment again after a human resolved the problem."""
    return PaymentIntentRead.model_validate(await service.retry_posting(intent_id))


@router.post(
    "/payments/{intent_id}/attach",
    response_model=PaymentIntentRead,
    dependencies=[Depends(can_transact), Depends(has_gateway)],
)
async def attach_document(
    intent_id: int,
    doctype: str = Query(description="Sales Invoice or Purchase Invoice"),
    docname: str = Query(description="The ERPNext document name"),
    service: PaymentGatewayService = Depends(get_payment_gateway_service),
) -> PaymentIntentRead:
    """Match an orphaned payment to the invoice it belongs to, then post it."""
    intent = service.attach_document(intent_id, doctype, docname)
    return PaymentIntentRead.model_validate(await service.refresh(intent))
