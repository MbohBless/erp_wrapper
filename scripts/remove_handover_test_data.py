"""Remove the records left by the handover verification run.

    docker compose cp scripts/remove_handover_test_data.py erpnext-backend:/tmp/rm.py
    echo 'exec(open("/tmp/rm.py").read(), globals())' \\
      | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console

Submitted documents cannot simply be deleted — ERPNext requires cancelling
first, which also reverses the GL and stock entries they created. Order matters:
a payment references an invoice, so the payment goes first, and the item cannot
go while a batch or a stock ledger entry still points at it.

Everything is matched on the HANDOVER prefix. Nothing else is touched, and a
record that is already gone is skipped rather than raising.

Note the `globals()` in the invocation above: `exec(source)` alone runs where
locals and globals differ, so a name bound at the top of this file is invisible
to a function defined further down.
"""

import frappe

PREFIX = "HANDOVER"
CUSTOMER = "Handover Check Clinic"


def drop(doctype, name):
    if not name or not frappe.db.exists(doctype, name):
        return
    try:
        doc = frappe.get_doc(doctype, name)
        # docstatus 1 == submitted; it must be cancelled before it can go, and
        # cancelling is what reverses its ledger impact.
        if getattr(doc, "docstatus", 0) == 1:
            doc.cancel()
            frappe.db.commit()
        frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        frappe.db.commit()
        print("  removed %s %s" % (doctype, name))
    except Exception as exc:
        print("  COULD NOT remove %s %s: %s" % (doctype, name, str(exc)[:120]))


print("removing handover test records…")

# Payments first: they reference the invoice.
for pe in frappe.get_all(
    "Payment Entry", filters={"party": CUSTOMER}, pluck="name"
):
    drop("Payment Entry", pe)

for si in frappe.get_all(
    "Sales Invoice", filters={"customer": CUSTOMER}, pluck="name"
):
    drop("Sales Invoice", si)

# Stock entries hold the item; the item cannot go until they do.
for se in frappe.get_all("Stock Entry", pluck="name"):
    rows = frappe.get_all(
        "Stock Entry Detail",
        filters={"parent": se, "item_code": ["like", PREFIX + "%"]},
        pluck="name",
    )
    if rows:
        drop("Stock Entry", se)

for mv in frappe.get_all(
    "Maintenance Visit", filters={"customer": CUSTOMER}, pluck="name"
):
    drop("Maintenance Visit", mv)

for batch in frappe.get_all(
    "Batch", filters={"name": ["like", PREFIX + "%"]}, pluck="name"
):
    drop("Batch", batch)

for item in frappe.get_all(
    "Item", filters={"item_code": ["like", PREFIX + "%"]}, pluck="name"
):
    drop("Item", item)

drop("Customer", CUSTOMER)

print()
print("remaining: customers=%d items=%d invoices=%d payments=%d gl=%d visits=%d" % (
    frappe.db.count("Customer"),
    frappe.db.count("Item"),
    frappe.db.count("Sales Invoice"),
    frappe.db.count("Payment Entry"),
    frappe.db.count("GL Entry"),
    frappe.db.count("Maintenance Visit"),
))
print("DONE")
