"""Unit tests for the ERP integration wrapper functions (against a fake client)."""

import pytest

from integrations.erpnext import (
    create_customer,
    create_invoice,
    create_purchase,
    get_balance_sheet,
    get_income_statement,
)
from tests.fakes import FakeERPNextClient


@pytest.fixture()
def erp():
    return FakeERPNextClient()


async def test_create_customer(erp):
    doc = await create_customer(erp, customer_name="Douala Clinic", tax_id="M123")
    assert doc["name"] == "Douala Clinic"
    assert doc["doctype"] == "Customer"
    assert doc["customer_type"] == "Company"
    assert doc["tax_id"] == "M123"
    # No customer_group at all when none was chosen. It used to default to the
    # tree root, which ERPNext refuses on a document — so every caller that did
    # not pass one was guaranteed a 417. Omitted, ERPNext applies its own.
    assert "customer_group" not in doc

    chosen = await create_customer(
        erp, customer_name="CHU Yaoundé", customer_group="Hospital"
    )
    assert chosen["customer_group"] == "Hospital"


async def test_create_invoice_submits(erp):
    doc = await create_invoice(
        erp,
        customer="Douala Clinic",
        items=[{"item_code": "THERMO-001", "qty": 2, "rate": 2500}],
    )
    assert doc["doctype"] == "Sales Invoice"
    assert doc["customer"] == "Douala Clinic"
    assert doc["items"][0]["item_code"] == "THERMO-001"
    assert doc["docstatus"] == 1  # submitted


async def test_create_invoice_draft_when_not_submitting(erp):
    doc = await create_invoice(
        erp,
        customer="Douala Clinic",
        items=[{"item_code": "THERMO-001", "qty": 1, "rate": 2500}],
        submit=False,
    )
    assert doc["docstatus"] == 0


async def test_create_purchase_submits(erp):
    doc = await create_purchase(
        erp,
        supplier="Acme Medical Ltd",
        items=[{"item_code": "THERMO-001", "qty": 10, "rate": 1500}],
        bill_no="INV-9",
    )
    assert doc["doctype"] == "Purchase Invoice"
    assert doc["supplier"] == "Acme Medical Ltd"
    assert doc["bill_no"] == "INV-9"
    assert doc["docstatus"] == 1


async def test_get_balance_sheet_fiscal_year(erp):
    result = await get_balance_sheet(erp, company="Equimed", fiscal_year="2026")
    assert result["report_name"] == "Balance Sheet"
    assert erp.last_report["filters"]["company"] == "Equimed"
    assert erp.last_report["filters"]["filter_based_on"] == "Fiscal Year"
    assert erp.last_report["filters"]["fiscal_year"] == "2026"


async def test_get_income_statement_date_range(erp):
    result = await get_income_statement(
        erp, company="Equimed", from_date="2026-01-01", to_date="2026-06-30"
    )
    assert result["report_name"] == "Profit and Loss Statement"
    filters = erp.last_report["filters"]
    assert filters["filter_based_on"] == "Date Range"
    assert filters["period_start_date"] == "2026-01-01"
    assert filters["period_end_date"] == "2026-06-30"
