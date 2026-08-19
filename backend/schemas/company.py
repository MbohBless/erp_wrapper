"""Company / branding profile schemas (Pydantic v2)."""

from pydantic import BaseModel, ConfigDict


class CompanyProfileBase(BaseModel):
    display_name: str = ""
    legal_name: str = ""
    tagline: str = "Medical Equipment Distribution"
    address_line: str = ""
    city: str = "Douala"
    country: str = "Cameroon"
    phone: str = ""
    email: str = ""
    website: str = ""
    rc_number: str = ""
    niu: str = ""
    currency: str = "XAF"
    signatory_name: str = ""
    signatory_title: str = "Authorized Signatory"
    accent_color: str = "#416180"
    logo_data_url: str = ""


class CompanyProfileUpdate(CompanyProfileBase):
    """Full replacement of the editable branding fields."""


class CompanyProfileRead(CompanyProfileBase):
    model_config = ConfigDict(from_attributes=True)
