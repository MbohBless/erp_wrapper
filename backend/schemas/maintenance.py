"""Maintenance ticket schemas (Pydantic V2). Proxy over the ERPNext Maintenance Visit DocType."""

from typing import Literal

from pydantic import BaseModel, Field

MaintenanceStatus = Literal[
    "Open", "Scheduled", "In Progress", "Completed", "Cancelled"
]


class MaintenanceBase(BaseModel):
    customer: str = Field(min_length=1)
    equipment: str | None = None  # serial number of the serviced device
    engineer: str | None = None
    visit_date: str | None = None
    description: str | None = None
    parts_used: str | None = None
    status: MaintenanceStatus = "Open"
    customer_signed: bool = False


class MaintenanceCreate(MaintenanceBase):
    pass


class MaintenanceUpdate(BaseModel):
    customer: str | None = None
    equipment: str | None = None
    engineer: str | None = None
    visit_date: str | None = None
    description: str | None = None
    parts_used: str | None = None
    status: MaintenanceStatus | None = None
    customer_signed: bool | None = None


class CompleteRequest(BaseModel):
    parts_used: str | None = None
    signed: bool = True  # customer signature captured on completion


class MaintenanceRead(MaintenanceBase):
    id: str  # ERPNext Maintenance Visit name (service ticket number)
