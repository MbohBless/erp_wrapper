"""Provisioning: creating and destroying a tenant's ERPNext site.

Behind a Protocol for two reasons. First, the two products provision very
differently — a shared-bench SaaS tenant is ``bench new-site``, a dedicated
instance is a whole compose stack — and the tenant lifecycle code should not
care which. Second, provisioning is the one operation in this system that is
slow, stateful and destructive, so it must be substitutable with a no-op in
tests and in dev.

``NoopProvisioner`` is the default. It records intent and changes nothing, so
an operator can drive the full lifecycle before any infrastructure exists.
"""

import asyncio
import shlex
from typing import Protocol

from config import settings
from models.tenant import Tenant


class ProvisioningError(RuntimeError):
    """A provisioning step failed. The tenant is left in its prior status."""


class Provisioner(Protocol):
    async def create_site(self, tenant: Tenant, admin_password: str) -> list[str]:
        """Create the tenant's ERPNext site. Must be idempotent."""
        ...

    async def drop_site(self, tenant: Tenant) -> list[str]:
        """Destroy the tenant's ERPNext site. Irreversible."""
        ...

    async def backup_site(self, tenant: Tenant) -> list[str]:
        """Take a backup of the tenant's site."""
        ...


class NoopProvisioner:
    """Records what would happen without touching infrastructure."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def create_site(self, tenant: Tenant, admin_password: str) -> list[str]:  # noqa: ARG002
        self.calls.append(("create_site", tenant.id))
        return [
            f"[noop] would create ERPNext site '{tenant.erpnext_site or tenant.id}'",
            "[noop] set PROVISIONER=bench to run this for real",
        ]

    async def drop_site(self, tenant: Tenant) -> list[str]:
        self.calls.append(("drop_site", tenant.id))
        return [f"[noop] would drop ERPNext site '{tenant.erpnext_site or tenant.id}'"]

    async def backup_site(self, tenant: Tenant) -> list[str]:
        self.calls.append(("backup_site", tenant.id))
        return [f"[noop] would back up ERPNext site '{tenant.erpnext_site or tenant.id}'"]


class FrappeBenchProvisioner:
    """Drives a Frappe bench over ``docker exec``.

    Requires the Docker socket inside this container, which is a real privilege
    escalation risk — anything that can reach this API can, transitively, run
    commands on the host's Docker daemon. Run the control plane on its own
    network, never expose ``/internal`` publicly, and prefer a dedicated
    provisioning worker if the platform grows past a handful of tenants.
    """

    def __init__(self, container: str | None = None, db_root_password: str = "") -> None:
        self.container = container or settings.bench_container
        self.db_root_password = db_root_password

    async def _run(self, *args: str) -> tuple[int, str]:
        cmd = ["docker", "exec", self.container, *args]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(
                proc.communicate(), timeout=settings.provision_timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise ProvisioningError(
                f"'{shlex.join(cmd)}' timed out after "
                f"{settings.provision_timeout_seconds}s"
            ) from exc
        return proc.returncode or 0, out.decode("utf-8", "replace").strip()

    async def create_site(self, tenant: Tenant, admin_password: str) -> list[str]:
        site = tenant.erpnext_site or f"{tenant.id}.{settings.erpnext_site_suffix}"
        messages: list[str] = []

        code, out = await self._run("bench", "--site", site, "version")
        if code == 0:
            messages.append(f"site '{site}' already exists — skipping creation")
            return messages

        code, out = await self._run(
            "bench",
            "new-site",
            site,
            "--db-root-password",
            self.db_root_password,
            "--admin-password",
            admin_password,
            "--install-app",
            "erpnext",
            "--no-mariadb-socket",
        )
        if code != 0:
            raise ProvisioningError(f"bench new-site failed for '{site}':\n{out}")
        messages.append(f"created ERPNext site '{site}'")
        return messages

    async def drop_site(self, tenant: Tenant) -> list[str]:
        site = tenant.erpnext_site or f"{tenant.id}.{settings.erpnext_site_suffix}"
        # Always take a backup first: drop-site is not recoverable and an
        # offboarding customer may still ask for their data afterwards.
        messages = await self.backup_site(tenant)
        code, out = await self._run(
            "bench", "drop-site", site,
            "--db-root-password", self.db_root_password,
            "--force",
        )
        if code != 0:
            raise ProvisioningError(f"bench drop-site failed for '{site}':\n{out}")
        messages.append(f"dropped ERPNext site '{site}'")
        return messages

    async def backup_site(self, tenant: Tenant) -> list[str]:
        site = tenant.erpnext_site or f"{tenant.id}.{settings.erpnext_site_suffix}"
        code, out = await self._run("bench", "--site", site, "backup", "--with-files")
        if code != 0:
            raise ProvisioningError(f"bench backup failed for '{site}':\n{out}")
        return [f"backed up ERPNext site '{site}'"]


def build_provisioner() -> Provisioner:
    if settings.provisioner == "bench":
        return FrappeBenchProvisioner()
    return NoopProvisioner()
