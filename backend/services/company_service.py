"""Business logic for the company/branding profile."""

from repositories.company_repository import CompanyRepository
from schemas.company import CompanyProfileRead, CompanyProfileUpdate


class CompanyService:
    def __init__(self, repo: CompanyRepository) -> None:
        self.repo = repo

    def get_profile(self) -> CompanyProfileRead:
        return CompanyProfileRead.model_validate(self.repo.get())

    def update_profile(self, data: CompanyProfileUpdate) -> CompanyProfileRead:
        return CompanyProfileRead.model_validate(
            self.repo.update(data.model_dump())
        )
