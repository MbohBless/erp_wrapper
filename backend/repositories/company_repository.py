"""Data access for the singleton CompanyProfile (app DB)."""

from sqlalchemy.orm import Session

from models.company_profile import CompanyProfile

_SINGLETON_ID = 1


class CompanyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self) -> CompanyProfile:
        """Return the singleton profile, creating the default row if missing."""
        profile = self.db.get(CompanyProfile, _SINGLETON_ID)
        if profile is None:
            profile = CompanyProfile(id=_SINGLETON_ID)
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def update(self, fields: dict) -> CompanyProfile:
        profile = self.get()
        for key, value in fields.items():
            setattr(profile, key, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile
