"""Health / readiness endpoints (infrastructure, not business logic)."""

from fastapi import APIRouter, Depends

from integrations.erpnext import ERPNextClient, get_erpnext_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe — the API process is up."""
    return {"status": "ok"}


@router.get("/health/erpnext")
async def erpnext_health(
    client: ERPNextClient = Depends(get_erpnext_client),
) -> dict:
    """Readiness probe — can the API reach ERPNext?"""
    reachable = await client.ping()
    return {"erpnext": "reachable" if reachable else "unreachable"}
