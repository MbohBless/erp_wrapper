"""Control-plane integration client.

The second (and only other) outbound HTTP boundary in the backend. Kept in
``integrations/`` for the same reason as ``erpnext.py``: everything that leaves
this process over the network lives in one directory, so the blast radius of an
outbound call is reviewable in one place.

Used only when ``TENANCY_MODE=multi``. Self-hosted deployments never import a
live instance of this — they use the static resolver instead.
"""

from typing import Any

import httpx

from config import settings


class ControlPlaneError(RuntimeError):
    """The control plane is unreachable or returned an error."""


class ControlPlaneClient:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.base_url = (base_url or settings.control_plane_url).rstrip("/")
        self._token = token or settings.control_plane_token
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._token:
            headers["X-Internal-Token"] = self._token
        return headers

    async def resolve_tenant(self, host: str) -> dict[str, Any] | None:
        """Look up a tenant by request host. ``None`` when no tenant matches."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/internal/tenants/resolve",
                    params={"host": host},
                    headers=self._headers(),
                )
        except httpx.RequestError as exc:  # pragma: no cover - network failure
            raise ControlPlaneError(f"Control plane unreachable: {exc}") from exc

        if resp.status_code == 404:
            return None
        if not resp.is_success:  # pragma: no cover - defensive
            raise ControlPlaneError(
                f"Control plane error ({resp.status_code}): {resp.text}"
            )
        return resp.json()
