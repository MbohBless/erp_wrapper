"""Calls into a tenant app instance's ``/internal`` API.

The control plane owns *who* a tenant is; the tenant app owns that tenant's
users, branding and profile rows. Provisioning therefore ends with a callback
here rather than the control plane reaching into the app's database — the two
services keep separate schemas and neither writes to the other's tables.
"""

from typing import Any

import httpx

from config import settings


class TenantAppError(RuntimeError):
    """The tenant app rejected or could not serve an internal call."""


class TenantAppClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = (base_url or settings.tenant_app_url).rstrip("/")
        self._token = token or settings.internal_api_token
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Accept": "application/json", "X-Internal-Token": self._token}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        if not self._token:
            raise TenantAppError(
                "INTERNAL_API_TOKEN is not configured; refusing to call the "
                "tenant app without authentication."
            )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(
                    method, f"{self.base_url}{path}", headers=self._headers(), **kwargs
                )
        except httpx.RequestError as exc:
            raise TenantAppError(f"Tenant app unreachable: {exc}") from exc

        if not resp.is_success:
            detail = resp.text
            try:
                detail = resp.json().get("detail", detail)
            except (ValueError, AttributeError):
                pass
            raise TenantAppError(f"Tenant app error ({resp.status_code}): {detail}")
        return resp.json()

    async def bootstrap(
        self,
        tenant_id: str,
        *,
        admin_email: str,
        admin_password: str,
        admin_name: str,
        company_name: str,
        app_name: str = "",
    ) -> dict:
        """Create the workspace's first administrator and default settings."""
        return await self._request(
            "POST",
            f"/internal/tenants/{tenant_id}/bootstrap",
            json={
                "admin_email": admin_email,
                "admin_password": admin_password,
                "admin_name": admin_name,
                "company_name": company_name,
                "app_name": app_name,
            },
        )

    async def purge(self, tenant_id: str) -> dict:
        """Erase the workspace's app-DB footprint."""
        return await self._request("DELETE", f"/internal/tenants/{tenant_id}")
