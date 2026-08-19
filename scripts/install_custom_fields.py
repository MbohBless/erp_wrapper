"""Create the Custom Fields the application depends on. No demo data.

    docker compose cp scripts/install_custom_fields.py erpnext-backend:/tmp/cf.py
    echo 'exec(open("/tmp/cf.py").read())' \
      | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console

Run this on every fresh site, before the app is used. The API stores anything
ERPNext has no native field for on a `custom_*` Custom Field; without them,
writes silently drop those attributes — a customer saves with no phone number
and nothing reports an error.

Split out of scripts/seed_erpnext.py, which does this *and* loads demo records.
A client's instance needs the fields and none of the records.

Idempotent: create_custom_fields skips fields that already exist.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# ---------------------------------------------------------------- Custom fields
DATA = {"fieldtype": "Data"}
create_custom_fields({
    "Customer": [
        {"fieldname": "custom_contact_person", "label": "Contact Person", **DATA, "insert_after": "customer_name"},
        {"fieldname": "custom_phone", "label": "Phone", **DATA, "insert_after": "custom_contact_person"},
        {"fieldname": "custom_email", "label": "Email", **DATA, "insert_after": "custom_phone"},
        {"fieldname": "custom_address", "label": "Address", "fieldtype": "Small Text", "insert_after": "custom_email"},
    ],
    "Supplier": [
        {"fieldname": "custom_contact_person", "label": "Contact Person", **DATA, "insert_after": "supplier_name"},
        {"fieldname": "custom_phone", "label": "Phone", **DATA, "insert_after": "custom_contact_person"},
        {"fieldname": "custom_email", "label": "Email", **DATA, "insert_after": "custom_phone"},
        {"fieldname": "custom_address", "label": "Address", "fieldtype": "Small Text", "insert_after": "custom_email"},
        {"fieldname": "custom_lead_time_days", "label": "Lead Time (days)", "fieldtype": "Int", "insert_after": "custom_address"},
    ],
    "Item": [
        {"fieldname": "custom_barcode", "label": "Barcode", **DATA, "insert_after": "item_name"},
        {"fieldname": "custom_manufacturer", "label": "Manufacturer", **DATA, "insert_after": "custom_barcode"},
        {"fieldname": "custom_purchase_price", "label": "Purchase Price", "fieldtype": "Currency", "insert_after": "custom_manufacturer"},
        {"fieldname": "custom_selling_price", "label": "Selling Price", "fieldtype": "Currency", "insert_after": "custom_purchase_price"},
    ],
    # A sale brokered by an agent, invoiced at a price below the product's own
    # selling price. The customer is billed the lower figure and nobody is owed
    # a payout — the agent's income is the spread — so this is a *discount with
    # a reason attached*, not ERPNext's `sales_partner` commission (which posts
    # an expense and a liability). Recording the reason is the whole point: the
    # give-away is otherwise indistinguishable from a typo in the rate.
    "Sales Invoice": [
        {"fieldname": "custom_is_commissioned", "label": "Commissioned Sale",
         "fieldtype": "Check", "insert_after": "remarks"},
        {"fieldname": "custom_commission_agent", "label": "Commission Agent",
         **DATA, "insert_after": "custom_is_commissioned",
         "depends_on": "eval:doc.custom_is_commissioned"},
    ],
    "Serial No": [
        {"fieldname": "custom_installation_date", "label": "Installation Date", "fieldtype": "Date", "insert_after": "warranty_expiry_date"},
        {"fieldname": "custom_status", "label": "Operational Status", **DATA, "insert_after": "custom_installation_date"},
    ],
    "Maintenance Visit": [
        {"fieldname": "custom_serial_no", "label": "Equipment Serial", **DATA, "insert_after": "customer_name"},
        {"fieldname": "custom_engineer", "label": "Engineer", **DATA, "insert_after": "custom_serial_no"},
        {"fieldname": "custom_description", "label": "Description", "fieldtype": "Small Text", "insert_after": "custom_engineer"},
        {"fieldname": "custom_parts_used", "label": "Parts Used", "fieldtype": "Small Text", "insert_after": "custom_description"},
        {"fieldname": "custom_status", "label": "Ticket Status", **DATA, "insert_after": "custom_parts_used"},
        {"fieldname": "custom_customer_signed", "label": "Customer Signed", "fieldtype": "Check", "insert_after": "custom_status"},
    ],
})
print("custom fields ok")
frappe.db.commit()
frappe.clear_cache()
print("DONE — custom fields installed")
