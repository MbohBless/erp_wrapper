"""Set the customer groups this business actually sells to.

    docker compose cp scripts/configure_customer_groups.py erpnext-backend:/tmp/cg.py
    echo 'exec(open("/tmp/cg.py").read(), globals())' \\
      | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console

ERPNext ships generic groups — Commercial, Government, Non Profit — which say
nothing about a medical-equipment distributor's customers. This replaces them
with the segments the business is actually organised around.

It matters beyond labelling: the dashboard's revenue-by-segment chart groups by
Customer Group, so these names are what the client sees when they ask "where is
our revenue coming from?". Generic groups make that chart useless.

Groups are created as **leaf** nodes under the tree root. ERPNext refuses a
group node on a transaction, so a customer can only ever be assigned a leaf.

Safe to re-run. A shipped group still in use by a customer is left alone rather
than deleted — reassign those first if you want it gone.
"""

import frappe

WANTED = [
    "Hospital",
    "Health Center",
    "Central Labs",
    "NGOs",
    "Individual",
]

# ERPNext defaults that mean nothing here. Removed only when unused.
UNWANTED = ["Commercial", "Government", "Non Profit"]

ROOT = "All Customer Groups"


def main():
    if not frappe.db.exists("Customer Group", ROOT):
        print("no '%s' root — is this an ERPNext site with the setup wizard run?" % ROOT)
        return

    print("--- creating the groups this business sells to " + "-" * 24)
    for name in WANTED:
        if frappe.db.exists("Customer Group", name):
            # Make sure a pre-existing one is selectable rather than a group.
            if frappe.db.get_value("Customer Group", name, "is_group"):
                frappe.db.set_value("Customer Group", name, "is_group", 0)
                print("  %-16s existed as a GROUP node — made selectable" % name)
            else:
                print("  %-16s already present" % name)
            continue
        doc = frappe.get_doc({
            "doctype": "Customer Group",
            "customer_group_name": name,
            "parent_customer_group": ROOT,
            "is_group": 0,
        })
        doc.insert(ignore_permissions=True)
        print("  %-16s created" % name)

    print()
    print("--- removing the generic defaults " + "-" * 37)
    for name in UNWANTED:
        if not frappe.db.exists("Customer Group", name):
            continue
        in_use = frappe.db.count("Customer", {"customer_group": name})
        if in_use:
            print("  %-16s KEPT — %d customer(s) still use it" % (name, in_use))
            continue
        try:
            frappe.delete_doc("Customer Group", name, force=True,
                              ignore_permissions=True)
            print("  %-16s removed" % name)
        except Exception as exc:
            print("  %-16s could not remove: %s" % (name, str(exc)[:90]))

    frappe.db.commit()
    frappe.clear_cache()

    print()
    selectable = frappe.get_all(
        "Customer Group", filters={"is_group": 0}, pluck="name", order_by="name"
    )
    print("selectable customer groups now: %s" % ", ".join(selectable))
    print("DONE")


main()
