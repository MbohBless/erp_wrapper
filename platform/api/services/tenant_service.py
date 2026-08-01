"""Tenant lifecycle business logic.

The state machine, in one place:

    pending --provision--> provisioning --> active
    active  --suspend----> suspended  --resume--> active
    any     --archive----> archived   --purge---> (deleted)

Two rules hold throughout:

* Status is only ever advanced after the underlying work succeeded. A failed
  ``bench new-site`` leaves the tenant in ``pending``, never in ``active``.
* Every transition is audited with the operator who caused it.
"""

import json
from datetime import datetime, timezone

from fastapi import HTTPException, status as http_status

from config import settings
from integrations.tenant_app import TenantAppClient, TenantAppError
from models.audit import (
    ACTION_DOMAIN_ADDED,
    ACTION_DOMAIN_REMOVED,
    ACTION_PLAN_CHANGED,
    ACTION_TENANT_ARCHIVED,
    ACTION_TENANT_CREATED,
    ACTION_TENANT_PROVISIONED,
    ACTION_TENANT_PURGED,
    ACTION_TENANT_RESUMED,
    ACTION_TENANT_SUSPENDED,
    ACTION_TENANT_UPDATED,
)
from models.plan import FEATURE_CUSTOM_DOMAIN
from models.tenant import (
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_PENDING,
    STATUS_PROVISIONING,
    STATUS_SUSPENDED,
    Tenant,
    TenantDomain,
)
from repositories.audit_repository import AuditRepository
from repositories.plan_repository import PlanRepository, features_of
from repositories.tenant_repository import TenantRepository
from schemas.tenant import (
    ProvisionResult,
    ResolvedTenant,
    TenantCreate,
    TenantRead,
    TenantUpdate,
)
from services.provisioning import Provisioner, ProvisioningError
from utils.crypto import decrypt, encrypt


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TenantService:
    def __init__(
        self,
        tenants: TenantRepository,
        plans: PlanRepository,
        audit: AuditRepository,
        provisioner: Provisioner,
        tenant_app: TenantAppClient,
        actor_email: str = "system",
    ) -> None:
        self.tenants = tenants
        self.plans = plans
        self.audit = audit
        self.provisioner = provisioner
        self.tenant_app = tenant_app
        self.actor = actor_email

    # --- Reads ----------------------------------------------------------
    def _require(self, tenant_id: str) -> Tenant:
        tenant = self.tenants.get(tenant_id)
        if tenant is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Workspace not found")
        return tenant

    def _read(self, tenant: Tenant) -> TenantRead:
        return TenantRead(
            id=tenant.id,
            name=tenant.name,
            status=tenant.status,
            plan_code=tenant.plan_code,
            contact_name=tenant.contact_name,
            contact_email=tenant.contact_email,
            country=tenant.country,
            notes=tenant.notes,
            erpnext_url=tenant.erpnext_url,
            erpnext_site=tenant.erpnext_site,
            erpnext_api_key=tenant.erpnext_api_key,
            has_erpnext_secret=bool(tenant.erpnext_api_secret_enc),
            suspended_reason=tenant.suspended_reason,
            suspended_at=tenant.suspended_at,
            provisioned_at=tenant.provisioned_at,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            domains=[
                {
                    "host": d.host,
                    "is_primary": d.is_primary,
                    "verified_at": d.verified_at,
                }
                for d in tenant.domains
            ],
            primary_host=tenant.primary_host,
        )

    def get(self, tenant_id: str) -> TenantRead:
        return self._read(self._require(tenant_id))

    def list(self, **filters) -> list[Tenant]:
        return self.tenants.list(**filters)

    def stats(self) -> dict:
        counts = self.tenants.count_by_status()
        return {
            "total": sum(counts.values()),
            "by_status": counts,
            "active": counts.get(STATUS_ACTIVE, 0),
            "suspended": counts.get(STATUS_SUSPENDED, 0),
        }

    # --- Create ---------------------------------------------------------
    def create(self, data: TenantCreate) -> TenantRead:
        if self.tenants.get(data.id) is not None:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                f"Workspace '{data.id}' already exists.",
            )
        if self.plans.get(data.plan_code) is None:
            raise HTTPException(
                http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Unknown plan '{data.plan_code}'.",
            )

        host = f"{data.id}.{settings.base_domain}"
        if self.tenants.get_domain(host) is not None:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT, f"Domain '{host}' is already in use."
            )

        tenant = Tenant(
            id=data.id,
            name=data.name,
            status=STATUS_PENDING,
            plan_code=data.plan_code,
            contact_name=data.contact_name,
            contact_email=str(data.contact_email or ""),
            country=data.country,
            notes=data.notes,
            # Blank coordinates mean "shared bench": one ERPNext, one site per
            # workspace, resolved by the Host header the tenant app sends.
            erpnext_url=data.erpnext_url or settings.default_erpnext_url,
            erpnext_site=data.erpnext_site
            or f"{data.id}.{settings.erpnext_site_suffix}",
            erpnext_api_key=data.erpnext_api_key,
            erpnext_api_secret_enc=encrypt(data.erpnext_api_secret),
        )
        tenant.domains.append(TenantDomain(host=host, is_primary=True, verified_at=_now()))
        self.tenants.add(tenant)

        self.audit.record(
            self.actor,
            ACTION_TENANT_CREATED,
            tenant.id,
            json.dumps({"name": tenant.name, "plan": tenant.plan_code, "host": host}),
        )
        return self._read(tenant)

    # --- Provision ------------------------------------------------------
    async def provision(self, tenant_id: str, data: TenantCreate | None = None,
                        admin_email: str = "", admin_password: str = "",
                        admin_name: str = "Administrator") -> ProvisionResult:
        """Create the ERPNext site and bootstrap the workspace's first admin.

        Idempotent: re-running against an active workspace re-checks both steps
        rather than failing, because the usual reason to re-run is that the
        first attempt died halfway.
        """
        tenant = self._require(tenant_id)
        if data is not None:
            admin_email = admin_email or str(data.admin_email)
            admin_password = admin_password or data.admin_password
            admin_name = data.admin_name or admin_name
        if not admin_email or not admin_password:
            raise HTTPException(
                http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                "An administrator email and password are required to provision.",
            )

        previous_status = tenant.status
        tenant.status = STATUS_PROVISIONING
        self.tenants.save(tenant)

        messages: list[str] = []
        try:
            messages += await self.provisioner.create_site(tenant, admin_password)
        except ProvisioningError as exc:
            tenant.status = previous_status
            self.tenants.save(tenant)
            raise HTTPException(http_status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

        bootstrapped = False
        try:
            result = await self.tenant_app.bootstrap(
                tenant.id,
                admin_email=admin_email,
                admin_password=admin_password,
                admin_name=admin_name,
                company_name=tenant.name,
                app_name=tenant.name,
            )
            bootstrapped = True
            messages.append(
                "created workspace administrator"
                if result.get("admin_created")
                else "workspace administrator already existed"
            )
        except TenantAppError as exc:
            # The site exists but the workspace has no admin — leave it in
            # provisioning so it stays locked and visibly incomplete.
            messages.append(f"bootstrap failed: {exc}")
            self.tenants.save(tenant)
            self.audit.record(
                self.actor, ACTION_TENANT_PROVISIONED, tenant.id,
                json.dumps({"ok": False, "messages": messages}),
            )
            raise HTTPException(http_status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

        tenant.status = STATUS_ACTIVE
        tenant.provisioned_at = _now()
        tenant.suspended_reason = ""
        tenant.suspended_at = None
        self.tenants.save(tenant)

        self.audit.record(
            self.actor, ACTION_TENANT_PROVISIONED, tenant.id,
            json.dumps({"ok": True, "messages": messages}),
        )
        return ProvisionResult(
            tenant=self._read(tenant),
            provisioned=True,
            bootstrapped=bootstrapped,
            messages=messages,
        )

    # --- Update ---------------------------------------------------------
    def update(self, tenant_id: str, data: TenantUpdate) -> TenantRead:
        tenant = self._require(tenant_id)
        changed: dict[str, object] = {}

        if data.plan_code is not None and data.plan_code != tenant.plan_code:
            if self.plans.get(data.plan_code) is None:
                raise HTTPException(
                    http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Unknown plan '{data.plan_code}'.",
                )
            self.audit.record(
                self.actor, ACTION_PLAN_CHANGED, tenant.id,
                json.dumps({"from": tenant.plan_code, "to": data.plan_code}),
            )
            tenant.plan_code = data.plan_code
            changed["plan_code"] = data.plan_code

        for field in ("name", "contact_name", "country", "notes",
                      "erpnext_url", "erpnext_site", "erpnext_api_key"):
            value = getattr(data, field)
            if value is not None:
                setattr(tenant, field, value)
                changed[field] = value
        if data.contact_email is not None:
            tenant.contact_email = str(data.contact_email)
            changed["contact_email"] = tenant.contact_email
        if data.erpnext_api_secret is not None:
            tenant.erpnext_api_secret_enc = encrypt(data.erpnext_api_secret)
            changed["erpnext_api_secret"] = "***"

        self.tenants.save(tenant)
        if changed:
            self.audit.record(
                self.actor, ACTION_TENANT_UPDATED, tenant.id, json.dumps(changed)
            )
        return self._read(tenant)

    # --- Suspend / resume -----------------------------------------------
    def suspend(self, tenant_id: str, reason: str) -> TenantRead:
        """The kill switch. Takes effect within the tenant app's cache TTL."""
        tenant = self._require(tenant_id)
        if tenant.status == STATUS_ARCHIVED:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT, "Archived workspaces cannot be suspended."
            )
        tenant.status = STATUS_SUSPENDED
        tenant.suspended_reason = reason
        tenant.suspended_at = _now()
        self.tenants.save(tenant)
        self.audit.record(
            self.actor, ACTION_TENANT_SUSPENDED, tenant.id, json.dumps({"reason": reason})
        )
        return self._read(tenant)

    def resume(self, tenant_id: str) -> TenantRead:
        tenant = self._require(tenant_id)
        if tenant.status != STATUS_SUSPENDED:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                f"Workspace is '{tenant.status}', not suspended.",
            )
        if tenant.provisioned_at is None:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "Workspace was never provisioned; provision it instead of resuming.",
            )
        tenant.status = STATUS_ACTIVE
        tenant.suspended_reason = ""
        tenant.suspended_at = None
        self.tenants.save(tenant)
        self.audit.record(self.actor, ACTION_TENANT_RESUMED, tenant.id)
        return self._read(tenant)

    def archive(self, tenant_id: str) -> TenantRead:
        """Take a workspace offline permanently, keeping its data for now."""
        tenant = self._require(tenant_id)
        tenant.status = STATUS_ARCHIVED
        tenant.suspended_reason = "Archived"
        tenant.suspended_at = _now()
        self.tenants.save(tenant)
        self.audit.record(self.actor, ACTION_TENANT_ARCHIVED, tenant.id)
        return self._read(tenant)

    async def purge(self, tenant_id: str, confirm_id: str) -> dict:
        """Delete a workspace and its data. Irreversible.

        Requires the caller to repeat the workspace id, and refuses anything
        that is not already archived — two deliberate speed bumps in front of
        the only operation here that destroys a customer's business records.
        """
        tenant = self._require(tenant_id)
        if confirm_id != tenant_id:
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                "Confirmation does not match the workspace id.",
            )
        if tenant.status != STATUS_ARCHIVED:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "Archive the workspace before purging it.",
            )

        messages: list[str] = []
        try:
            messages += await self.provisioner.drop_site(tenant)
        except ProvisioningError as exc:
            raise HTTPException(http_status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

        try:
            result = await self.tenant_app.purge(tenant.id)
            messages.append(f"removed {result.get('users_deleted', 0)} app user(s)")
        except TenantAppError as exc:
            messages.append(f"app-DB purge failed: {exc}")

        self.audit.record(
            self.actor, ACTION_TENANT_PURGED, tenant.id, json.dumps({"messages": messages})
        )
        self.tenants.delete(tenant)
        return {"tenant_id": tenant_id, "messages": messages}

    # --- Domains --------------------------------------------------------
    def add_domain(self, tenant_id: str, host: str, is_primary: bool) -> TenantRead:
        tenant = self._require(tenant_id)
        plan = self.plans.get(tenant.plan_code)
        if plan is None or FEATURE_CUSTOM_DOMAIN not in features_of(plan):
            raise HTTPException(
                http_status.HTTP_402_PAYMENT_REQUIRED,
                f"Custom domains are not included in the '{tenant.plan_code}' plan.",
            )
        if self.tenants.get_domain(host) is not None:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT, f"Domain '{host}' is already in use."
            )
        if is_primary:
            for existing in tenant.domains:
                existing.is_primary = False
        self.tenants.add_domain(
            TenantDomain(tenant_id=tenant.id, host=host, is_primary=is_primary)
        )
        self.tenants.save(tenant)
        self.audit.record(
            self.actor, ACTION_DOMAIN_ADDED, tenant.id, json.dumps({"host": host})
        )
        return self._read(tenant)

    def remove_domain(self, tenant_id: str, host: str) -> TenantRead:
        tenant = self._require(tenant_id)
        domain = self.tenants.get_domain(host)
        if domain is None or domain.tenant_id != tenant.id:
            raise HTTPException(
                http_status.HTTP_404_NOT_FOUND, f"Domain '{host}' is not on this workspace."
            )
        if len(tenant.domains) == 1:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                "A workspace must keep at least one domain.",
            )
        self.tenants.delete_domain(domain)
        self.audit.record(
            self.actor, ACTION_DOMAIN_REMOVED, tenant.id, json.dumps({"host": host})
        )
        return self._read(self._require(tenant_id))

    def verify_domain(self, tenant_id: str, host: str) -> TenantRead:
        """Mark a custom domain as pointing at us, unlocking TLS issuance."""
        tenant = self._require(tenant_id)
        domain = self.tenants.get_domain(host)
        if domain is None or domain.tenant_id != tenant.id:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Domain not found")
        domain.verified_at = _now()
        self.tenants.save(tenant)
        return self._read(tenant)

    # --- Internal (tenant app + reverse proxy) ---------------------------
    def resolve(self, host: str) -> ResolvedTenant | None:
        tenant = self.tenants.get_by_host(host)
        if tenant is None:
            return None
        plan = self.plans.get(tenant.plan_code)
        return ResolvedTenant(
            id=tenant.id,
            name=tenant.name,
            status=tenant.status,
            plan=tenant.plan_code,
            erpnext_url=tenant.erpnext_url,
            erpnext_site=tenant.erpnext_site or None,
            erpnext_api_key=tenant.erpnext_api_key,
            erpnext_api_secret=decrypt(tenant.erpnext_api_secret_enc),
            features=features_of(plan) if plan else [],
        )

    def authorize_tls(self, host: str) -> bool:
        """Caddy's on-demand-TLS ask endpoint.

        Answers "may I obtain a certificate for this hostname?". Only known,
        verified, non-archived domains qualify — otherwise anyone pointing DNS
        at us could make us request certificates on their behalf.
        """
        domain = self.tenants.get_domain(host)
        if domain is None or domain.verified_at is None:
            return False
        return domain.tenant.status != STATUS_ARCHIVED
