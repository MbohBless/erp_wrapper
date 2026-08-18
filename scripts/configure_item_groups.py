"""Restrict product categories to the two this business actually has.

    docker compose cp scripts/configure_item_groups.py erpnext-backend:/tmp/ig.py
    echo 'exec(open("/tmp/ig.py").read(), globals())' \
      | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console

A medical-equipment distributor sells two things: devices, and the consumables
that feed them. ERPNext ships Products / Raw Material / Sub Assemblies /
Services, which belong to a manufacturer and only give people ways to file the
same item under four different labels — after which no report can group by
category.

Creates the wanted groups, and retires ERPNext's defaults only when nothing uses
them. It does NOT reassign existing items: which of a client's products is
equipment and which is a consumable is their call, not a guess this script
should make.
"""

import frappe

WANTED = ["Equipment", "Consumable"]
UNWANTED = ["Products", "Raw Material", "Sub Assemblies", "Services"]
ROOT = "All Item Groups"


def main():
    print("--- categories this business uses " + "-" * 36)
    for name in WANTED:
        if frappe.db.exists("Item Group", name):
            if frappe.db.get_value("Item Group", name, "is_group"):
                frappe.db.set_value("Item Group", name, "is_group", 0)
                print("  %-16s existed as a GROUP node — made selectable" % name)
            else:
                print("  %-16s already present" % name)
            continue
        frappe.get_doc({
            "doctype": "Item Group",
            "item_group_name": name,
            "parent_item_group": ROOT,
            "is_group": 0,
        }).insert(ignore_permissions=True)
        print("  %-16s created" % name)

    print()
    print("--- retiring the manufacturer defaults " + "-" * 31)
    for name in UNWANTED:
        if not frappe.db.exists("Item Group", name):
            continue
        in_use = frappe.db.count("Item", {"item_group": name})
        if in_use:
            print("  %-16s KEPT — %d item(s) still use it" % (name, in_use))
            continue
        try:
            frappe.delete_doc("Item Group", name, force=True, ignore_permissions=True)
            print("  %-16s removed" % name)
        except Exception as exc:
            print("  %-16s could not remove: %s" % (name, str(exc)[:80]))

    frappe.db.commit()
    frappe.clear_cache()

    print()
    selectable = frappe.get_all(
        "Item Group", filters={"is_group": 0}, pluck="name", order_by="name"
    )
    print("selectable categories now: %s" % ", ".join(selectable))

    # The root is not a category. Items sitting on it were filed before there
    # was anything better to choose, and no report can group by "everything".
    stranded = frappe.get_all("Item", filters={"item_group": ROOT},
                              fields=["item_code", "item_name"])
    if stranded:
        print()
        print("%d item(s) still on the tree root '%s' — these need a category:"
              % (len(stranded), ROOT))
        for it in stranded:
            print("   %-14s %s" % (it["item_code"], it["item_name"]))
    print("DONE")


main()
