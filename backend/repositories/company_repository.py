"""Data access for the per-tenant CompanyProfile (app DB)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.company_profile import CompanyProfile


class CompanyRepository:
    def __init__(self, db: Session, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def get(self) -> CompanyProfile:
        """Return this tenant's profile, creating the default row if missing."""
        profile = self.db.scalar(
            select(CompanyProfile).where(CompanyProfile.tenant_id == self.tenant_id)
        )
        if profile is None:
            profile = CompanyProfile(tenant_id=self.tenant_id)
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def update(self, fields: dict) -> CompanyProfile:
        profile = self.get()
        for key, value in fields.items():
            # tenant_id is owned by the repository, never by a payload.
            if key == "tenant_id":
                continue
            setattr(profile, key, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def delete(self) -> None:
        profile = self.db.scalar(
            select(CompanyProfile).where(CompanyProfile.tenant_id == self.tenant_id)
        )
        if profile is not None:
            self.db.delete(profile)
            self.db.commit()
