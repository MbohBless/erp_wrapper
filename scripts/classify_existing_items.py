"""Assign a category to items filed on the tree root.

    docker compose cp scripts/classify_existing_items.py erpnext-backend:/tmp/ci.py
    echo 'exec(open("/tmp/ci.py").read(), globals())' \
      | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console

A one-off migration for items created before the category field was a
constrained choice. The mapping is explicit per SKU rather than inferred from
the name at runtime: this classification drives every future category report,
and a rule like "contains Analyzer" would silently mis-file the first product
that breaks the pattern.

Only touches items currently on the tree root. An item someone has already
categorised is left exactly as it is.
"""

import frappe

ROOT = "All Item Groups"

MAPPING = {
    # Instruments — the devices themselves.
    "AutoSe-0001": "Equipment",   # AutoSense Blood Glucose Meter
    "GER-0001":    "Equipment",   # Gazelle Electrophoresis Reader
    "LabU-0002":   "Equipment",   # LabUReader 2 Pro Urine Analyzer
    "UM0001":      "Equipment",   # Urised Mini Microscopy Analyzer
    "DocU-0001":   "Equipment",   # DocUReader 2 Pro Urine Analyzer
    "DiaSA-0001":  "Equipment",   # DiaSpect TM Analyzer
    # Consumables — what the instruments run on.
    "GHBC-0002":   "Consumable",  # Gazelle HB Variant Cartridges
    "UMC-0002":    "Consumable",  # Urised Mini Cuvette
    "ABGTS-0002":  "Consumable",  # AutoSense Blood Glucose Test Strips
    "LU11P-0001":  "Consumable",  # Labstrips U11 Plus
    "LUS-0002":    "Consumable",  # LabStrip U11 Smart
    "DHBC-0002":   "Consumable",  # DiaSpect HB Cuvette
}


def main():
    for group in set(MAPPING.values()):
        if not frappe.db.exists("Item Group", group):
            print("category '%s' does not exist — run configure_item_groups.py first" % group)
            return

    stranded = frappe.get_all(
        "Item", filters={"item_group": ROOT}, fields=["item_code", "item_name"]
    )
    if not stranded:
        print("no items on the tree root; nothing to do")
        return

    print("--- assigning " + "-" * 52)
    changed, skipped = 0, []
    for it in stranded:
        sku = it["item_code"]
        target = MAPPING.get(sku)
        if not target:
            skipped.append(it)
            continue
        frappe.db.set_value("Item", sku, "item_group", target)
        print("  %-14s %-42s -> %s" % (sku, it["item_name"][:42], target))
        changed += 1

    frappe.db.commit()
    frappe.clear_cache()

    print()
    if skipped:
        print("NOT in the mapping — still uncategorised, assign in the app:")
        for it in skipped:
            print("   %-14s %s" % (it["item_code"], it["item_name"]))
        print()

    print("--- catalogue by category " + "-" * 41)
    for row in frappe.db.sql(
        "select item_group, count(*) from tabItem group by item_group order by 2 desc",
        as_list=True,
    ):
        print("  %-18s %d item(s)" % (row[0], row[1]))
    print()
    print("changed: %d" % changed)
    print("DONE")


main()
