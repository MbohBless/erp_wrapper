"""In-memory fake of ERPNextClient for tests.

Implements the generic DocType methods the repositories rely on, storing
documents in a dict keyed by their ERPNext `name`.
"""

import itertools

from integrations.erpnext import ERPNextNotFound

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
            elif op == "like":
                needle = str(val).strip("%").lower()
                if needle not in str(dv or "").lower():
                    return False
        return True

    async def list_documents(
        self, doctype, fields=None, filters=None, limit=20, start=0, order_by=None
    ):
        docs = [d for d in self.store.values() if self._matches(d, filters)]
        return docs[start : start + limit]

    async def get_document(self, doctype, name):
        if name not in self.store:
            raise ERPNextNotFound(f"{doctype} {name} not found")
        return self.store[name]

    async def create_document(self, doctype, data):
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
        self.store[name].update(data)
        return self.store[name]

    async def delete_document(self, doctype, name):
        if name not in self.store:
            raise ERPNextNotFound(f"{doctype} {name} not found")
        del self.store[name]

    async def submit_document(self, doctype, name):
        if name not in self.store:
            raise ERPNextNotFound(f"{doctype} {name} not found")
        self.store[name]["docstatus"] = 1
        return self.store[name]

    async def run_report(self, report_name, filters=None):
        # Record the call so tests can assert report name + filters.
        self.last_report = {"report_name": report_name, "filters": filters or {}}
        return {"report_name": report_name, "filters": filters or {}, "result": []}
