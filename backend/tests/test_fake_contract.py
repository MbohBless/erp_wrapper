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
    # Deliberately doctypes with no mandatory-field rules: this is about
    # separation, and a half-built Sales Invoice is now refused on its own
    # merits, which is the point of the rest of this file.
    await fake.create_document("Widget", {"name": "W-1"})
    await fake.create_document("Gadget", {"name": "G-1"})

    assert [d["name"] for d in await fake.list_documents("Widget")] == ["W-1"]
    assert [d["name"] for d in await fake.list_documents("Gadget")] == ["G-1"]


# --- The rules the fake now enforces, because ERPNext does ---------------
#
# Each of these stands for a defect that shipped green. The fake accepting what
# ERPNext refuses is not a missing test — it is a passing test that proves
# nothing, which is worse, because it reads as coverage.

from datetime import date

from integrations.erpnext import ERPNextError


async def test_a_list_query_returns_no_child_table():
    """`GET /api/resource/{doctype}` returns parent fields only. Handing back
    `items` made invoice lines look present in tests while the real list gave
    nothing — and the totals, which live on the parent, kept looking right."""
    fake = FakeERPNextClient()
    await fake.create_document("Sales Invoice", {
        "name": "SI-1", "customer": "CHU", "grand_total": 5000,
        "items": [{"item_code": "THERMO-001", "qty": 2, "rate": 2500}],
    })

    listed = (await fake.list_documents("Sales Invoice"))[0]
    assert "items" not in listed
    assert listed["grand_total"] == 5000          # the parent field is there

    fetched = await fake.get_document("Sales Invoice", "SI-1")
    assert len(fetched["items"]) == 1              # by id, the lines are


async def test_a_submitted_document_cannot_be_edited():
    """Which is why correcting one is cancel-then-amend."""
    fake = FakeERPNextClient()
    await fake.create_document("Sales Invoice", {"name": "SI-1", "customer": "CHU",
                                                 "items": [{"item_code": "X"}]})
    await fake.submit_document("Sales Invoice", "SI-1")

    with pytest.raises(ERPNextError, match="submitted"):
        await fake.update_document("Sales Invoice", "SI-1", {"customer": "Someone else"})


async def test_posting_date_is_ignored_without_set_posting_time():
    """The trap that silently posted backdated invoices to today."""
    fake = FakeERPNextClient()
    await fake.create_document("Sales Invoice", {
        "name": "SI-1", "customer": "CHU", "items": [{"item_code": "X"}],
        "posting_date": "2026-03-04"})
    assert (await fake.get_document("Sales Invoice", "SI-1"))["posting_date"] \
        == date.today().isoformat()

    await fake.create_document("Sales Invoice", {
        "name": "SI-2", "customer": "CHU", "items": [{"item_code": "X"}],
        "posting_date": "2026-03-04", "set_posting_time": 1})
    assert (await fake.get_document("Sales Invoice", "SI-2"))["posting_date"] \
        == "2026-03-04"


async def test_a_tree_root_cannot_be_selected():
    """"All Customer Groups" and friends are containers. Defaulting a field to
    one broke customer creation and filed twelve items under a category nothing
    can group by."""
    fake = FakeERPNextClient()
    with pytest.raises(ERPNextError, match="group node"):
        await fake.create_document("Customer", {"customer_name": "CHU",
                                                "customer_group": "All Customer Groups"})
    with pytest.raises(ERPNextError, match="group node"):
        await fake.create_document("Item", {"item_code": "X",
                                            "item_group": "All Item Groups"})

    # Creating the container itself is legitimate — ERPNext ships these records.
    await fake.create_document("Item Group", {"name": "All Item Groups", "is_group": 1})


async def test_a_document_missing_a_mandatory_field_is_refused():
    fake = FakeERPNextClient()
    with pytest.raises(ERPNextError, match="customer is mandatory"):
        await fake.create_document("Sales Invoice", {"items": [{"item_code": "X"}]})
    with pytest.raises(ERPNextError, match="items is mandatory"):
        await fake.create_document("Sales Invoice", {"customer": "CHU"})


async def test_a_mandatory_child_row_must_be_complete():
    """A Maintenance Visit needs a `purposes` row carrying `service_person` and
    `work_done`. An empty row saved happily here and failed against every real
    instance — maintenance tickets could not be created at all."""
    fake = FakeERPNextClient()
    with pytest.raises(ERPNextError, match="missing service_person"):
        await fake.create_document("Maintenance Visit", {
            "customer": "CHU", "purposes": [{"work_done": "Replaced the pump"}]})

    await fake.create_document("Maintenance Visit", {
        "customer": "CHU",
        "purposes": [{"service_person": "Eng. Ngassa", "work_done": "Replaced the pump"}]})
