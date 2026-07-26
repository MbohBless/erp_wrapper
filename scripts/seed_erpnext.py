"""Seed EquiMed demo data into ERPNext + create the app's Custom Fields + API keys.

Run inside the erpnext-backend container via bench console:
    docker compose cp scripts/seed_erpnext.py erpnext-backend:/tmp/seed.py
    echo "exec(open('/tmp/seed.py').read())" | \
      docker compose exec -T erpnext-backend bench --site equimed.local console

Idempotent: skips records that already exist. `frappe` is provided by the console.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_days, today, flt

log = []
def note(msg): log.append(msg); print(msg)

COMPANY = frappe.defaults.get_global_default("company") or frappe.get_all("Company", pluck="name")[0]
def _first(dt, filters=None):
    r = frappe.get_all(dt, filters=filters or {}, pluck="name", limit=1)
    return r[0] if r else None

ITEM_GROUP = "Products" if frappe.db.exists("Item Group", "Products") else "All Item Groups"
CUST_GROUP = "Commercial" if frappe.db.exists("Customer Group", "Commercial") else "All Customer Groups"
SUPP_GROUP = _first("Supplier Group", {"is_group": 0}) or "All Supplier Groups"
TERRITORY = "Cameroon" if frappe.db.exists("Territory", "Cameroon") else "All Territories"
UOM = "Nos" if frappe.db.exists("UOM", "Nos") else _first("UOM")
WAREHOUSE = (frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0, "warehouse_name": "Stores"}, "name")
             or frappe.get_all("Warehouse", filters={"company": COMPANY, "is_group": 0}, pluck="name")[0])
note(f"company={COMPANY} item_group={ITEM_GROUP} warehouse={WAREHOUSE} uom={UOM}")

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
note("custom fields ok")

def save(doc):
    d = frappe.get_doc(doc)
    d.insert(ignore_permissions=True)
    return d

# ---------------------------------------------------------------- Customers
CUSTOMERS = [
    ("CHU Yaoundé", "Dr. Nkeng", "+237699100001", "contact@chu-yaounde.cm"),
    ("Hôpital Général de Douala", "Dr. Eboa", "+237699100002", "info@hgd.cm"),
    ("Clinique du Littoral", "Mme Ndreville", "+237699100003", "accueil@littoral.cm"),
    ("Pharmacie Centrale", "M. Fotso", "+237699100004", "vente@pharmacentrale.cm"),
    ("Hôpital Laquintinie", "Dr. Mballa", "+237699100005", "dg@laquintinie.cm"),
    ("Polyclinique Bonanjo", "Dr. Sonkeng", "+237699100006", "contact@bonanjo.cm"),
    ("Centre Médical la Grâce", "Mme Abena", "+237699100007", "cmg@grace.cm"),
]
for name, contact, phone, email in CUSTOMERS:
    if frappe.db.exists("Customer", name):
        continue
    save({"doctype": "Customer", "customer_name": name, "customer_group": CUST_GROUP,
          "customer_type": "Company", "territory": TERRITORY,
          "custom_contact_person": contact, "custom_phone": phone, "custom_email": email,
          "custom_address": "Douala / Yaoundé, Cameroon"})
note(f"customers: {frappe.db.count('Customer')}")

# ---------------------------------------------------------------- Suppliers
SUPPLIERS = [
    ("Sanofi Cameroun", "M. Diallo", "+237677200001", "sales@sanofi.cm", 21),
    ("GSK Africa", "Ms. Owens", "+237677200002", "orders@gsk.cm", 30),
    ("Cinpharm", "M. Kamdem", "+237677200003", "contact@cinpharm.cm", 7),
    ("Laborex Cameroun", "Mme Tchana", "+237677200004", "info@laborex.cm", 10),
    ("Ubipharm Cameroun", "M. Njoya", "+237677200005", "cm@ubipharm.com", 14),
]
for name, contact, phone, email, lead in SUPPLIERS:
    if frappe.db.exists("Supplier", name):
        continue
    save({"doctype": "Supplier", "supplier_name": name, "supplier_group": SUPP_GROUP,
          "supplier_type": "Company", "custom_contact_person": contact, "custom_phone": phone,
          "custom_email": email, "custom_lead_time_days": lead, "custom_address": "Cameroon"})
note(f"suppliers: {frappe.db.count('Supplier')}")

# ---------------------------------------------------------------- Items
def make_item(code, name, buy, sell, manufacturer, serial=False, batch=False):
    if frappe.db.exists("Item", code):
        return
    save({"doctype": "Item", "item_code": code, "item_name": name, "item_group": ITEM_GROUP,
          "stock_uom": UOM, "is_stock_item": 1, "has_serial_no": 1 if serial else 0,
          "has_batch_no": 1 if batch else 0,
          "create_new_batches_automatically": 1 if batch else 0,
          "custom_manufacturer": manufacturer, "custom_purchase_price": buy,
          "custom_selling_price": sell, "custom_barcode": f"60012{abs(hash(code)) % 10000000:07d}"})

SIMPLE = [  # sellable / stockable, no serial/batch
    ("GLOVE-NITRILE", "Nitrile Gloves (box)", 3000, 4500, "Acme"),
    ("MASK-SURGICAL", "Surgical Mask (box)", 1500, 2500, "Acme"),
    ("SYRINGE-5ML", "Syringe 5ml (box)", 1800, 3000, "MediCorp"),
    ("THERMO-DIGITAL", "Digital Thermometer", 1500, 2500, "OmronMed"),
    ("PARA-1G-INJ", "Paracetamol 1g Injection", 400, 700, "Cinpharm"),
    ("AMOX-500", "Amoxicillin 500mg", 120, 250, "GSK"),
]
BATCHED = [
    ("MET-850", "Metformin 850mg", 90, 180, "Sanofi"),
    ("INSULIN-GLAR", "Insulin Glargine 100IU", 4200, 6500, "Sanofi"),
    ("ACT-COMBI", "Artemether/Lumefantrine", 600, 1100, "Cinpharm"),
]
EQUIP = [
    ("VENTILATOR-VG70", "Ventilator VG70", 4500000, 6200000, "Dräger"),
    ("ECG-MON-12", "ECG Monitor 12-lead", 1200000, 1800000, "GE Healthcare"),
    ("PATIENT-MON", "Patient Monitor", 900000, 1400000, "Mindray"),
]
for c, n, b, s, m in SIMPLE: make_item(c, n, b, s, m)
for c, n, b, s, m in BATCHED: make_item(c, n, b, s, m, batch=True)
for c, n, b, s, m in EQUIP: make_item(c, n, b, s, m, serial=True)
note(f"items: {frappe.db.count('Item')}")

# ---------------------------------------------------------------- Batches
BATCHES = [
    ("MET-7781", "MET-850", add_days(today(), 34)),
    ("MET-7782", "MET-850", add_days(today(), 210)),
    ("INS-2210", "INSULIN-GLAR", add_days(today(), 95)),
    ("ACT-9901", "ACT-COMBI", add_days(today(), 60)),
]
for bid, item, exp in BATCHES:
    if frappe.db.exists("Batch", bid):
        continue
    try:
        save({"doctype": "Batch", "batch_id": bid, "item": item, "expiry_date": exp})
    except Exception as e:
        note(f"  batch {bid} skipped: {e}")
note(f"batches: {frappe.db.count('Batch')}")

# ---------------------------------------------------------------- Stock (receipts)
def receipt(item, qty, rate):
    try:
        se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
                             "company": COMPANY, "to_warehouse": WAREHOUSE,
                             "items": [{"item_code": item, "qty": qty, "t_warehouse": WAREHOUSE, "basic_rate": rate}]})
        se.insert(ignore_permissions=True); se.submit()
    except Exception as e:
        note(f"  receipt {item} skipped: {e}")

if not frappe.db.get_value("Bin", {"item_code": "GLOVE-NITRILE"}):
    for item, qty, rate in [("GLOVE-NITRILE", 500, 3000), ("MASK-SURGICAL", 8, 1500),
                            ("SYRINGE-5ML", 5, 1800), ("THERMO-DIGITAL", 40, 1500),
                            ("PARA-1G-INJ", 6, 400), ("AMOX-500", 120, 120)]:
        receipt(item, qty, rate)
note(f"stock bins: {frappe.db.count('Bin')}")

# ---------------------------------------------------------------- Equipment (Serial No)
SERIALS = [
    ("VENT-0001", "VENTILATOR-VG70", "CHU Yaoundé", "Installed", add_days(today(), -120)),
    ("VENT-0002", "VENTILATOR-VG70", None, "In Store", None),
    ("ECG-0001", "ECG-MON-12", "Hôpital Général de Douala", "Installed", add_days(today(), -40)),
    ("ECG-0002", "ECG-MON-12", "Clinique du Littoral", "Under Repair", add_days(today(), -300)),
    ("PMON-0001", "PATIENT-MON", "Polyclinique Bonanjo", "Installed", add_days(today(), -60)),
]
for sn, item, cust, status, inst in SERIALS:
    if frappe.db.exists("Serial No", sn):
        continue
    try:
        save({"doctype": "Serial No", "serial_no": sn, "item_code": item,
              "customer": cust, "custom_status": status,
              "custom_installation_date": inst,
              "warranty_expiry_date": add_days(today(), 540)})
    except Exception as e:
        note(f"  serial {sn} skipped: {e}")
note(f"serial nos: {frappe.db.count('Serial No')}")

# ---------------------------------------------------------------- Maintenance
if not frappe.db.exists("Sales Person", "Field Service"):
    try:
        save({"doctype": "Sales Person", "sales_person_name": "Field Service", "is_group": 0,
              "parent_sales_person": _first("Sales Person", {"is_group": 1})})
    except Exception as e:
        note(f"  sales person skipped: {e}")

VISITS = [
    ("CHU Yaoundé", "VENT-0001", "Eng. Talla", "Ventilator annual calibration", "Scheduled", -2, False),
    ("Hôpital Général de Douala", "ECG-0001", "Eng. Fon", "ECG electrode replacement", "Completed", -6, True),
    ("Clinique du Littoral", "ECG-0002", "Eng. Talla", "Repair power module", "In Progress", -1, False),
]
for cust, sn, eng, desc, status, offset, signed in VISITS:
    exists = frappe.get_all("Maintenance Visit", filters={"customer": cust, "custom_serial_no": sn}, limit=1)
    if exists:
        continue
    try:
        mv = frappe.get_doc({"doctype": "Maintenance Visit", "customer": cust,
                             "mntc_date": add_days(today(), offset), "completion_status": "Partially Completed",
                             "custom_serial_no": sn, "custom_engineer": eng, "custom_description": desc,
                             "custom_status": status, "custom_customer_signed": 1 if signed else 0,
                             "purposes": [{"description": desc, "work_done": desc, "service_person": "Field Service"}]})
        mv.insert(ignore_permissions=True)
    except Exception as e:
        note(f"  visit {sn} skipped: {e}")
note(f"maintenance visits: {frappe.db.count('Maintenance Visit')}")

# ---------------------------------------------------------------- Sales Invoices
def sales_invoice(cust, items, pdate, ddate):
    try:
        si = frappe.get_doc({"doctype": "Sales Invoice", "company": COMPANY, "customer": cust,
                             "posting_date": pdate, "set_posting_time": 1, "due_date": ddate, "update_stock": 0,
                             "items": [{"item_code": i, "qty": q, "rate": r} for i, q, r in items]})
        si.insert(ignore_permissions=True); si.submit()
        return si.name
    except Exception as e:
        note(f"  sales invoice skipped: {e}"); return None

if frappe.db.count("Sales Invoice") == 0:
    sales_invoice("CHU Yaoundé", [("GLOVE-NITRILE", 200, 4500), ("PARA-1G-INJ", 500, 700)], today(), add_days(today(), 30))
    sales_invoice("Hôpital Général de Douala", [("MASK-SURGICAL", 300, 2500), ("SYRINGE-5ML", 200, 3000)], today(), add_days(today(), 30))
    sales_invoice("Clinique du Littoral", [("AMOX-500", 400, 250)], add_days(today(), -10), add_days(today(), -5))  # overdue
    sales_invoice("Pharmacie Centrale", [("MET-850", 300, 180), ("AMOX-500", 200, 250)], add_days(today(), -20), add_days(today(), -12))  # overdue
    sales_invoice("Hôpital Laquintinie", [("THERMO-DIGITAL", 15, 2500)], add_days(today(), -3), add_days(today(), 27))
    sales_invoice("Polyclinique Bonanjo", [("INSULIN-GLAR", 40, 6500)], add_days(today(), -1), add_days(today(), 29))
    sales_invoice("Centre Médical la Grâce", [("ACT-COMBI", 250, 1100)], add_days(today(), -25), add_days(today(), 5))
note(f"sales invoices: {frappe.db.count('Sales Invoice')}")

# ---------------------------------------------------------------- Purchase Invoices
def purchase_invoice(supp, items, bill_no, pdate):
    try:
        pi = frappe.get_doc({"doctype": "Purchase Invoice", "company": COMPANY, "supplier": supp,
                             "posting_date": pdate, "set_posting_time": 1, "bill_no": bill_no, "update_stock": 0,
                             "items": [{"item_code": i, "qty": q, "rate": r} for i, q, r in items]})
        pi.insert(ignore_permissions=True); pi.submit()
        return pi.name
    except Exception as e:
        note(f"  purchase invoice skipped: {e}"); return None

if frappe.db.count("Purchase Invoice") == 0:
    purchase_invoice("Sanofi Cameroun", [("MET-850", 1000, 90), ("INSULIN-GLAR", 100, 4200)], "SAN-4471", add_days(today(), -8))
    purchase_invoice("Cinpharm", [("PARA-1G-INJ", 2000, 400), ("ACT-COMBI", 1500, 600)], "CIN-2201", add_days(today(), -12))
    purchase_invoice("GSK Africa", [("AMOX-500", 3000, 120)], "GSK-9982", add_days(today(), -5))
    purchase_invoice("Laborex Cameroun", [("GLOVE-NITRILE", 800, 3000), ("MASK-SURGICAL", 1000, 1500)], "LAB-3310", add_days(today(), -3))
note(f"purchase invoices: {frappe.db.count('Purchase Invoice')}")

# ---------------------------------------------------------------- API key for the backend
# Only mint keys the first time — re-running must not invalidate the secret the
# backend is already configured with.
user = frappe.get_doc("User", "Administrator")
frappe.db.commit()
print("\n================ SEED COMPLETE ================")
if not user.api_key:
    user.api_key = frappe.generate_hash(length=15)
    api_secret = frappe.generate_hash(length=15)
    user.api_secret = api_secret
    user.flags.ignore_permissions = True
    user.save()
    frappe.db.commit()
    print("ERPNEXT_API_KEY=" + user.api_key)
    print("ERPNEXT_API_SECRET=" + api_secret)
    print("(put these in .env, then: docker compose up -d backend)")
else:
    print("API key already set (" + user.api_key + "); keeping existing secret.")
print("==============================================")
