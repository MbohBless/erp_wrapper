"""The fake must not be more permissive than ERPNext.

Its job is to stand in for a system that *refuses* things. Every time it has
quietly accepted what ERPNext rejects, the tests relying on that behaviour
carried on passing while proving nothing — comparison operators matching every
row, filters ignored wholesale, paging ignored. Those were not gaps in coverage;
they were tests that looked like coverage.

So this file tests the test double.
"""

import pytest

from tests.fakes import FakeERPNextClient


def test_an_unimplemented_operator_raises_rather_than_matching_everything():
    """The failure mode being prevented: a filter nobody implemented silently
    letting every row through, so the assertion downstream passes for the wrong
    reason."""
    with pytest.raises(AssertionError, match="no 'between' filter operator"):
        FakeERPNextClient._matches({"qty": 5}, [["qty", "between", [1, 10]]])


@pytest.mark.parametrize(
    "doc, filters, expected",
    [
        ({"status": "Paid"}, [["status", "=", "Paid"]], True),
        ({"status": "Paid"}, [["status", "=", "Unpaid"]], False),
        ({"docstatus": 1}, [["docstatus", "!=", 2]], True),
        ({"docstatus": 2}, [["docstatus", "!=", 2]], False),
        ({"item": "A"}, [["item", "in", ["A", "B"]]], True),
        ({"item": "C"}, [["item", "in", ["A", "B"]]], False),
        # The filter the aged ledger depends on.
        ({"outstanding_amount": 500}, [["outstanding_amount", ">", 0]], True),
        ({"outstanding_amount": 0}, [["outstanding_amount", ">", 0]], False),
        # Dates are ISO strings; comparing them lexically is why ERPNext can
        # filter on them at all.
        ({"posting_date": "2025-12-01"}, [["posting_date", "<", "2026-01-01"]], True),
        ({"posting_date": "2026-02-01"}, [["posting_date", "<", "2026-01-01"]], False),
        ({"customer": "CHU Yaoundé"}, [["customer", "like", "%Yaound%"]], True),
        ({"customer": "Clinique"}, [["customer", "like", "%Yaound%"]], False),
    ],
)
def test_the_operators_it_does_implement_behave(doc, filters, expected):
    assert FakeERPNextClient._matches(doc, filters) is expected


async def test_paging_is_honoured():
    """A stub that ignored limit/start let a repository page through it forever,
    and made a partial read look complete."""
    fake = FakeERPNextClient()
    for i in range(7):
        await fake.create_document("Widget", {"name": f"W-{i}"})

    first = await fake.list_documents("Widget", limit=3, start=0)
    second = await fake.list_documents("Widget", limit=3, start=3)
    last = await fake.list_documents("Widget", limit=3, start=6)

    assert [d["name"] for d in first] == ["W-0", "W-1", "W-2"]
    assert [d["name"] for d in second] == ["W-3", "W-4", "W-5"]
    assert [d["name"] for d in last] == ["W-6"]


async def test_documents_of_another_doctype_are_not_returned():
    """Without this a repository writing to the wrong DocType still reads back
    what it expects, and the suite cannot tell two DocTypes apart."""
    fake = FakeERPNextClient()
    await fake.create_document("Sales Invoice", {"name": "SI-1"})
    await fake.create_document("Purchase Invoice", {"name": "PI-1"})

    assert [d["name"] for d in await fake.list_documents("Sales Invoice")] == ["SI-1"]
    assert [d["name"] for d in await fake.list_documents("Purchase Invoice")] == ["PI-1"]
