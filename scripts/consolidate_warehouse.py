"""Consolidate onto a single stock location.

    docker compose cp scripts/consolidate_warehouse.py erpnext-backend:/tmp/cw.py
    echo 'exec(open("/tmp/cw.py").read(), globals())' \
      | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console

A distribution business holds one kind of stock: finished devices. ERPNext ships
Stores / Work In Progress / Finished Goods for a manufacturer, and the extra
locations only create the chance of putting stock somewhere the next person does
not look.

Warehouses are DISABLED, never deleted. ERPNext keeps stock ledger entries
against a warehouse forever, so deleting one either fails or orphans history.
Disabling removes it from selection and is reversible; deletion is neither.

Order matters: nothing may still point at a warehouse when it is disabled, or
the next document created from that default fails validation.
"""

import frappe

KEEP_MATCH = "Finished Goods"


def main():
    company = frappe.get_all("Company", pluck="name")[0]
    leaves = frappe.get_all(
        "Warehouse",
        filters={"company": company, "is_group": 0},
        fields=["name", "disabled"],
        order_by="name",
    )
    keep = next((w["name"] for w in leaves if KEEP_MATCH.lower() in w["name"].lower()), None)
    if not keep:
        print("no '%s' warehouse found; refusing to guess which to keep" % KEEP_MATCH)
        return
    # Everything that is not the keeper, INCLUDING warehouses already disabled.
    # A default still pointing at a disabled warehouse is the dangerous case:
    # nothing complains until a document is created from that default and fails
    # validation. An earlier version only looked at warehouses it disabled
    # itself, and so walked straight past 13 item defaults left behind when the
    # warehouse was disabled by hand in the desk.
    others = [w["name"] for w in leaves if w["name"] != keep]
    already_off = [w["name"] for w in leaves if w["name"] != keep and w["disabled"]]

    print("keeping : %s" % keep)
    print("retiring: %s" % (", ".join(others) or "none"))
    if already_off:
        print("  (already disabled, but still referenced: %s)" % ", ".join(already_off))
    print()

    # Refuse to retire a warehouse that actually holds something. A cancelled
    # ledger row is harmless residue; a live quantity is stock someone counted.
    blocked = []
    for w in others:
        qty = frappe.db.sql(
            "select ifnull(sum(actual_qty),0) from tabBin where warehouse=%s", w
        )[0][0] or 0
        if abs(float(qty)) > 0.0001:
            blocked.append((w, qty))
    if blocked:
        for w, qty in blocked:
            print("  REFUSING %s — holds %s units. Move the stock first." % (w, qty))
        return

    # 1. Repoint anything that would otherwise default to a retired warehouse.
    moved = 0
    for row in frappe.get_all(
        "Item Default",
        filters={"default_warehouse": ["in", others]},
        fields=["name", "parent", "default_warehouse"],
    ):
        frappe.db.set_value("Item Default", row["name"], "default_warehouse", keep)
        moved += 1
    print("  item defaults repointed to %s: %d" % (keep, moved))

    # 2. The global default, before anything is disabled.
    current = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    if current in others:
        frappe.db.set_value("Stock Settings", "Stock Settings", "default_warehouse", keep)
        print("  Stock Settings default: %s -> %s" % (current, keep))
    else:
        print("  Stock Settings default already %s" % current)

    # 3. Now retire them.
    for w in others:
        if frappe.db.get_value("Warehouse", w, "disabled"):
            continue
        frappe.db.set_value("Warehouse", w, "disabled", 1)
        print("  disabled %s (kept, not deleted — ledger history survives)" % w)

    frappe.db.commit()
    frappe.clear_cache()

    print()
    active = frappe.get_all(
        "Warehouse",
        filters={"company": company, "is_group": 0, "disabled": 0},
        pluck="name",
    )
    print("selectable warehouses now: %s" % ", ".join(active))
    print("DONE")


main()
