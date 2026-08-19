"""Add one selectable customer group. Additive only.

    docker compose cp scripts/add_customer_group.py erpnext-backend:/tmp/acg.py
    echo 'exec(open("/tmp/acg.py").read(), globals())' \
      | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console

Deliberately separate from configure_customer_groups.py. That script also
*removes* ERPNext's generic defaults, which is right on a fresh install and
wrong once a client is entering data — a delete list is not something to run
near live records. This one only inserts, and refuses if the name already
exists.

The group is created as a leaf under the tree root: ERPNext rejects a group node
on a transaction, so only a leaf can be assigned to a customer.
"""

import frappe

NEW = "Sub Distributor"
ROOT = "All Customer Groups"


def main():
    if frappe.db.exists("Customer Group", NEW):
        is_group = frappe.db.get_value("Customer Group", NEW, "is_group")
        print("'%s' already exists (is_group=%s) — nothing to do" % (NEW, is_group))
        return

    if not frappe.db.exists("Customer Group", ROOT):
        print("no '%s' root; refusing to guess a parent" % ROOT)
        return

    before = frappe.get_all(
        "Customer Group", filters={"is_group": 0}, pluck="name", order_by="name"
    )

    doc = frappe.get_doc({
        "doctype": "Customer Group",
        "customer_group_name": NEW,
        "parent_customer_group": ROOT,
        "is_group": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.clear_cache()

    after = frappe.get_all(
        "Customer Group", filters={"is_group": 0}, pluck="name", order_by="name"
    )
    added = [g for g in after if g not in before]
    removed = [g for g in before if g not in after]

    print("added  : %s" % (added or "none"))
    print("removed: %s   <- must be empty" % (removed or "none"))
    print("groups now: %s" % ", ".join(after))


main()
