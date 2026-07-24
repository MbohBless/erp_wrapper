"""Equipment schemas (Pydantic V2). Proxy over the ERPNext Serial No DocType."""

from typing import Literal

from pydantic import BaseModel, Field

EquipmentStatus = Literal["In Store", "Installed", "Under Repair", "Decommissioned"]


class EquipmentBase(BaseModel):
    serial_no: str = Field(min_length=1, max_length=140)
    item_code: str = Field(min_length=1, max_length=140)
    customer: str | None = None
    installation_date: str | None = None
    warranty_expiry_date: str | None = None
    status: EquipmentStatus = "In Store"


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    item_code: str | None = Field(default=None, min_length=1, max_length=140)
    customer: str | None = None
    installation_date: str | None = None
    warranty_expiry_date: str | None = None
    status: EquipmentStatus | None = None


class InstallRequest(BaseModel):
    customer: str | None = None
    installation_date: str | None = None  # defaults to today when omitted


class EquipmentRead(EquipmentBase):
    id: str  # ERPNext Serial No name (== serial_no)
    item_name: str | None = None
