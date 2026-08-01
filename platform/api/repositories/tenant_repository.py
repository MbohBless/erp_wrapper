"""Tenant registry data access."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from models.tenant import Tenant, TenantDomain


class TenantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, tenant_id: str) -> Tenant | None:
        return self.db.get(Tenant, tenant_id)

    def get_by_host(self, host: str) -> Tenant | None:
        """Resolve a hostname to its tenant — the hot path for the SaaS plane."""
        domain = self.db.scalar(
            select(TenantDomain).where(TenantDomain.host == host.strip().lower())
        )
        return domain.tenant if domain else None

    def list(
        self,
        status: str | None = None,
        plan_code: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Tenant]:
        stmt = select(Tenant)
        if status:
            stmt = stmt.where(Tenant.status == status)
        if plan_code:
            stmt = stmt.where(Tenant.plan_code == plan_code)
        if search:
            needle = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Tenant.id).like(needle),
                    func.lower(Tenant.name).like(needle),
                    func.lower(Tenant.contact_email).like(needle),
                )
            )
        stmt = stmt.order_by(Tenant.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(stmt))

    def count_by_status(self) -> dict[str, int]:
        rows = self.db.execute(
            select(Tenant.status, func.count(Tenant.id)).group_by(Tenant.status)
        ).all()
        return {status: count for status, count in rows}

    def count_for_plan(self, plan_code: str) -> int:
        return int(
            self.db.scalar(
                select(func.count(Tenant.id)).where(Tenant.plan_code == plan_code)
            )
            or 0
        )

    def add(self, tenant: Tenant) -> Tenant:
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def save(self, tenant: Tenant) -> Tenant:
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def delete(self, tenant: Tenant) -> None:
        self.db.delete(tenant)
        self.db.commit()

    # --- Domains --------------------------------------------------------
    def get_domain(self, host: str) -> TenantDomain | None:
        return self.db.scalar(
            select(TenantDomain).where(TenantDomain.host == host.strip().lower())
        )

    def add_domain(self, domain: TenantDomain) -> TenantDomain:
        self.db.add(domain)
        self.db.commit()
        self.db.refresh(domain)
        return domain

    def delete_domain(self, domain: TenantDomain) -> None:
        self.db.delete(domain)
        self.db.commit()
