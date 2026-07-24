"""Helpers for translating between domain data and ERPNext payloads.

Centralises the small conversions every ERPNext-backed repository repeats:
numeric coercion, boolean -> 0/1, and date -> ISO string.
"""

from collections.abc import Iterable
from datetime import date
from typing import Any


def to_float(value: Any, default: float = 0.0) -> float:
    """Best-effort float coercion (ERPNext numbers arrive as strings/None)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_erpnext(
    data: dict,
    field_map: dict[str, str],
    *,
    bool_fields: Iterable[str] = (),
) -> dict:
    """Translate a dict of domain attributes into an ERPNext payload.

    - keys absent from ``field_map`` are dropped
    - attributes named in ``bool_fields`` are coerced to 1/0
    - ``date`` values are ISO-formatted
    """
    bools = set(bool_fields)
    payload: dict = {}
    for attr, value in data.items():
        target = field_map.get(attr)
        if target is None:
            continue
        if attr in bools:
            value = 1 if value else 0
        elif isinstance(value, date):
            value = value.isoformat()
        payload[target] = value
    return payload
