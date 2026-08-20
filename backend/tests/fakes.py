"""In-memory fake of ERPNextClient for tests.

Implements the generic DocType methods the repositories rely on, storing
documents in a dict keyed by their ERPNext `name`.
"""

import itertools
from datetime import date

from integrations.erpnext import ERPNextError, ERPNextNotFound

# ERPNext autoname field per DocType (used to derive the document `name`).
_NAME_FIELDS = (
    "supplier_name",
    "serial_no",
    "item_code",
    "warehouse_name",
    "batch_id",
    "customer_name",
    "name",
)


def _as_list_row(doc: dict) -> dict:
    """A list result, shaped as ERPNext returns one.

    Child tables are dropped. `GET /api/resource/{doctype}` returns parent
    fields only, so `items` is never there — a detail view has to fetch the
    document by id. Returning them here made an invoice's lines look present in
    tests while the real list gave back nothing, and the totals sitting on the
    parent kept looking right, so it read as a display glitch rather than
    missing data.

    Also a copy, not the stored dict: handing out the store lets a caller mutate
    it by accident and lets a repository "pass" by editing the database.
    """
    return {
        k: v
        for k, v in doc.items()
        if not (isinstance(v, list) and v and isinstance(v[0], dict))
    }


class FakeERPNextClient:
    def __init__(self) -> None:
        self.store: dict[str, dict] = {}
        self._seq = itertools.count(1)

    @staticmethod
    def _matches(doc: dict, filters) -> bool:
        for field, op, val in filters or []:
            dv = doc.get(field)
            if op == "=":
                if dv != val:
                    return False
            elif op == "!=":
                if dv == val:
                    return False
            elif op == "in":
                if dv not in (val or []):
                    return False
            elif op in (">", "<", ">=", "<="):
                # Comparisons were previously ignored, which quietly made the
                # fake *more* permissive than ERPNext: a filter like
                # ["outstanding_amount", ">", 0] matched every row, so a settled
                # invoice came back where the real thing excludes it — and any
                # test relying on that filter proved nothing.
                try:
                    left, right = float(dv or 0), float(val or 0)
                except (TypeError, ValueError):
                    # Dates arrive as ISO strings. Comparing them lexically is
                    # not a shortcut — it is why ERPNext can filter on them at
                    # all — but coercing them to float is not, and treating the
                    # failure as "no match" quietly drops every dated filter.
                    left, right = str(dv or ""), str(val or "")
                if op == ">" and not left > right:
                    return False
                if op == "<" and not left < right:
                    return False
                if op == ">=" and not left >= right:
                    return False
                if op == "<=" and not left <= right:
                    return False
            elif op == "like":
                needle = str(val).strip("%").lower()
                if needle not in str(dv or "").lower():
                    return False
            else:
                # Fail closed. An operator this fake does not implement used to
                # fall through and match every row, so a test exercising that
                # filter passed while proving nothing — which is exactly how
                # three filters the repositories already depended on went
                # unverified. A fake that is more permissive than the thing it
                # stands in for is worse than no fake: it converts a real
                # refusal into a green test.
                raise AssertionError(
                    f"FakeERPNextClient has no {op!r} filter operator "
                    f"(filtering {field!r}). Implement it here to match what "
                    "ERPNext does, rather than letting it match everything."
                )
        return True

    async def list_documents(
        self, doctype, fields=None, filters=None, limit=20, start=0, order_by=None
    ):
        # Filter by doctype. Without this the fake returns every document
        # regardless of type, so a repository that creates a supporting record
        # of another DocType silently corrupts an unrelated listing — and a
        # test suite that cannot tell two DocTypes apart cannot catch a
        # repository writing to the wrong one.
        docs = [
            d
            for d in self.store.values()
            if d.get("doctype") in (doctype, None) and self._matches(d, filters)
        ]
        return [_as_list_row(d) for d in docs[start : start + limit]]

    async def get_document(self, doctype, name):
        if name not in self.store:
            raise ERPNextNotFound(f"{doctype} {name} not found")
        return self.store[name]

    #: Fields ERPNext will not create a document without. Only the ones that
    #: have actually bitten: a document that saves in the fake and is rejected
    #: by the real thing is the whole failure mode this file exists to prevent.
    MANDATORY = {
        "Sales Invoice": ("customer", "items"),
        "Purchase Invoice": ("supplier", "items"),
        "Maintenance Visit": ("customer", "purposes"),
        "Journal Entry": ("company", "accounts"),
    }
    #: Child rows that are themselves incomplete without these. A Maintenance
    #: Visit with an empty `purposes` row saved happily here and failed against
    #: every real instance — maintenance tickets could not be created at all.
    MANDATORY_CHILD = {
        "Maintenance Visit": ("purposes", ("service_person", "work_done")),
    }
    #: Tree roots. Containers that hold branches; ERPNext refuses them on a
    #: transaction ("Cannot select a Group type…"). Defaulting a field to one
    #: broke customer creation and filed twelve items under a category nothing
    #: can group by.
    GROUP_NODES = frozenset(
        {"All Customer Groups", "All Item Groups", "All Warehouses"}
    )
    #: The fields that point *at* one of those trees.
    GROUP_LINK_FIELDS = (
        "customer_group", "item_group", "warehouse",
        "s_warehouse", "t_warehouse", "set_warehouse", "default_warehouse",
    )

    @staticmethod
    def _apply_posting_date(data: dict) -> dict:
        """ERPNext ignores a supplied `posting_date` unless `set_posting_time`
        is also set — it silently stamps today instead.

        Reproduced rather than honoured, because honouring it is what let
        backdating look like it worked: an invoice raised for last month saved,
        read back with the date asked for, and posted to the wrong period. The
        only way a test can catch that is if the fake does what ERPNext does.
        """
        if not data.get("posting_date") or data.get("set_posting_time"):
            return data
        return {**data, "posting_date": date.today().isoformat()}

    def _validate(self, doctype: str, data: dict) -> None:
        for field in self.MANDATORY.get(doctype, ()):
            if not data.get(field):
                raise ERPNextError(
                    f"{doctype}: {field} is mandatory", 417
                )
        child_field, required = self.MANDATORY_CHILD.get(doctype, (None, ()))
        if child_field:
            for row in data.get(child_field) or []:
                for field in required:
                    if not row.get(field):
                        raise ERPNextError(
                            f"{doctype}: {child_field} row is missing {field}",
                            417,
                        )
        # Only where a root is being *selected*. Creating the container itself
        # is legitimate — ERPNext ships these records — so the check is on the
        # link fields that point at one, not on every string in the payload.
        for field in self.GROUP_LINK_FIELDS:
            value = data.get(field)
            if isinstance(value, str) and value in self.GROUP_NODES:
                raise ERPNextError(
                    f"{doctype}: cannot select group node {value!r} for "
                    f"{field} — it is a container, not a selectable value",
                    417,
                )

    async def create_document(self, doctype, data):
        self._validate(doctype, data)
        data = self._apply_posting_date(data)
        # An amendment is named after the document it replaces: ERPNext appends
        # a counter, so ACC-SINV-2026-00007 becomes ACC-SINV-2026-00007-1. The
        # id changing is the part callers get wrong, so the fake reproduces it
        # rather than handing back an unrelated autoname.
        original = data.get("amended_from")
        if original:
            n = 1
            while f"{original}-{n}" in self.store:
                n += 1
            name = f"{original}-{n}"
        else:
            name = next((data[f] for f in _NAME_FIELDS if data.get(f)), None)
        if not name:
            # Autoname series (e.g. Stock Entry) — generate a deterministic id.
            name = f"{doctype}-{next(self._seq)}"
        doc = {**data, "name": name, "doctype": doctype, "docstatus": 0}
        self.store[name] = doc
        return doc

    async def update_document(self, doctype, name, data):
        if name not in self.store:
            raise ERPNextNotFound(f"{doctype} {name} not found")
        doc = self.store[name]
        if int(doc.get("docstatus") or 0) == 1:
            # ERPNext refuses this outright: a submitted document is immutable
            # except for `allow_on_submit` fields, which is why correcting one
            # means cancel-then-amend. Accepting it here would let an in-place
            # edit pass every test and fail on the first real invoice.
            raise ERPNextError(
                f"Cannot edit {doctype} {name}: it is submitted. Cancel and "
                "amend it instead.",
                417,
            )
        doc.update(data)
        return doc

    async def delete_document(self, doctype, name):
        if name not in self.store:
            raise ERPNextNotFound(f"{doctype} {name} not found")
        del self.store[name]

    async def submit_document(self, doctype, name):
        if name not in self.store:
            raise ERPNextNotFound(f"{doctype} {name} not found")
        self.store[name]["docstatus"] = 1
        return self.store[name]

    async def cancel_document(self, doctype, name):
        if name not in self.store:
            raise ERPNextNotFound(f"{doctype} {name} not found")
        doc = self.store[name]
        doc["docstatus"] = 2
        doc["status"] = "Cancelled"
        # ERPNext zeroes the outstanding amount when it reverses a document.
        # Without this the fake would let a guard that reads "how much has been
        # settled?" pass on a cancelled invoice where the real one refuses.
        doc["outstanding_amount"] = 0
        return doc

    async def run_report(self, report_name, filters=None):
        # Record the call so tests can assert report name + filters.
        self.last_report = {"report_name": report_name, "filters": filters or {}}
        return {"report_name": report_name, "filters": filters or {}, "result": []}

    async def call_method(self, method, args=None, http_method="POST"):
        args = args or {}
        if method.endswith("get_payment_entry"):
            return {
                "doctype": "Payment Entry",
                "payment_type": "Receive" if args.get("dt") == "Sales Invoice" else "Pay",
                "party_type": "Customer" if args.get("dt") == "Sales Invoice" else "Supplier",
                "party": "Test Party",
                "paid_amount": 1000,
                "received_amount": 1000,
                "posting_date": "2026-07-25",
                "references": [
                    {"reference_doctype": args.get("dt"), "reference_name": args.get("dn"),
                     "allocated_amount": 1000}
                ],
            }
        return None
