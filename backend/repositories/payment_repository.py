"""Payment data-access backed by the ERPNext Payment Entry DocType.

Payments are built with ERPNext's `get_payment_entry` helper (which auto-fills
the receivable/payable + cash/bank accounts), then submitted.
"""

from integrations.erpnext import ERPNextClient, ERPNextError
from schemas.payments import PaymentRead
from utils.mapping import to_float as _num

_GET_PE = "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry"
_LIST_FIELDS = [
    "name", "payment_type", "party_type", "party", "paid_amount",
    "posting_date", "mode_of_payment", "reference_no",
]


def _from_erpnext(doc: dict) -> PaymentRead:
    return PaymentRead(
        id=doc.get("name"),
        payment_type=doc.get("payment_type"),
        party_type=doc.get("party_type"),
        party=doc.get("party"),
        paid_amount=_num(doc.get("paid_amount") or doc.get("received_amount")),
        posting_date=doc.get("posting_date"),
        mode_of_payment=doc.get("mode_of_payment"),
        reference_no=doc.get("reference_no"),
    )


class PaymentRepository:
    DOCTYPE = "Payment Entry"

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def list(self, limit: int = 50, start: int = 0) -> list[PaymentRead]:
        docs = await self.client.list_documents(
            self.DOCTYPE, fields=_LIST_FIELDS, filters=[["docstatus", "=", 1]],
            limit=limit, start=start, order_by="posting_date desc",
        )
        return [_from_erpnext(doc) for doc in docs]

    async def record(
        self,
        reference_doctype: str,
        reference_name: str,
        amount: float | None = None,
        mode: str | None = None,
        posting_date: str | None = None,
        reference_no: str | None = None,
    ) -> PaymentRead:
        pe = await self.client.call_method(
            _GET_PE, {"dt": reference_doctype, "dn": reference_name}
        )
        if not pe:
            raise ERPNextError("Could not build a payment for this document", 502)

        if posting_date:
            # set_posting_time is required for ERPNext to honour posting_date at
            # all; without it the entry silently lands on today.
            pe["posting_date"] = posting_date
            pe["set_posting_time"] = 1
            pe["reference_date"] = posting_date
        if mode:
            pe["mode_of_payment"] = mode
            # Route the money through the account configured for that mode
            # (e.g. Cash -> the Caisse account) instead of the default bank.
            # Read the parent Mode of Payment doc (child tables aren't REST-queryable).
            try:
                mop = await self.client.get_document("Mode of Payment", mode)
            except ERPNextError:
                mop = {}
            acct = next(
                (r.get("default_account") for r in (mop.get("accounts") or [])
                 if r.get("company") == pe.get("company") and r.get("default_account")),
                None,
            )
            if acct:
                if pe.get("payment_type") == "Pay":
                    pe["paid_from"] = acct
                else:
                    pe["paid_to"] = acct
        if reference_no:
            pe["reference_no"] = reference_no
            pe.setdefault("reference_date", posting_date or pe.get("posting_date"))
        if amount is not None:
            pe["paid_amount"] = amount
            pe["received_amount"] = amount
            refs = pe.get("references") or []
            if refs:
                refs[0]["allocated_amount"] = amount

        doc = await self.client.create_document(self.DOCTYPE, pe)
        submitted = await self.client.submit_document(self.DOCTYPE, doc.get("name"))
        return _from_erpnext(submitted or doc)
