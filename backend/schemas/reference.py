"""Reference data schemas (Pydantic v2)."""

from pydantic import BaseModel


class ReferenceOptions(BaseModel):
    """Selectable values for form pickers.

    Every list contains only leaf nodes — ERPNext rejects group nodes on
    transactions, so offering them would offer failure.
    """

    customer_groups: list[str] = []
    supplier_groups: list[str] = []
    territories: list[str] = []
    item_groups: list[str] = []
    warehouses: list[str] = []
    uoms: list[str] = []
