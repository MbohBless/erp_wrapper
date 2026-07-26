import frappe
company="EquiMed"; CC="Main - E"; MARK="[SEED-OHADA-CYCLE]"
SUP="Ubipharm Cameroun"; CUST="Centre Médical la Grâce"

if frappe.db.exists("Journal Entry", {"company": company, "user_remark": ("like", "%"+MARK+"%")}):
    print("ALREADY_SEEDED"); raise SystemExit

def acc(num):
    return frappe.db.get_value("Account", {"company": company, "account_number": num}, "name")

missing=set()
def je(date, title, lines):
    doc = frappe.new_doc("Journal Entry")
    doc.posting_date = date; doc.company = company
    doc.user_remark = title + " " + MARK
    td=tc=0
    for num, dr, cr in lines:
        name = acc(num)
        if not name: missing.add(num); return None
        row = {"account": name, "debit_in_account_currency": dr, "credit_in_account_currency": cr}
        if num[0] in ("6","7","8"): row["cost_center"] = CC
        atype = frappe.db.get_value("Account", name, "account_type")
        if atype == "Payable": row["party_type"]="Supplier"; row["party"]=SUP
        elif atype == "Receivable": row["party_type"]="Customer"; row["party"]=CUST
        doc.append("accounts", row); td+=dr; tc+=cr
    assert round(td,2)==round(tc,2), (title, td, tc)
    doc.insert(); doc.submit(); return doc.name

plan = [
 ("2026-01-05","Apport en capital",            [("5211",15000000,0),("1013",0,15000000)]),
 ("2026-01-08","Emprunt bancaire",             [("5211",8000000,0),("162",0,8000000)]),
 ("2026-02-01","Acquisition materiel commercial",[("2413",3000000,0),("5211",0,3000000)]),
 ("2026-02-01","Acquisition licence logiciel", [("2122",1200000,0),("5211",0,1200000)]),
 ("2026-06-30","Dotation amort. licence",      [("6812",240000,0),("2812",0,240000)]),
 ("2026-02-15","Achats de marchandises",       [("6011",4000000,0),("4011",0,4000000)]),
 ("2026-03-10","Reglement fournisseurs",       [("4011",2500000,0),("5211",0,2500000)]),
 ("2026-03-31","Salaires du personnel",        [("6611",1800000,0),("5211",0,1500000),("422",0,300000)]),
 ("2026-03-31","Location du local",            [("6222",900000,0),("5211",0,900000)]),
 ("2026-04-05","Transports sur ventes",        [("612",350000,0),("5211",0,350000)]),
 ("2026-04-20","Patente et taxes",             [("6412",400000,0),("4421",0,400000)]),
 ("2026-05-15","Interets sur emprunt",         [("6712",600000,0),("5211",0,600000)]),
 ("2026-05-31","Escomptes obtenus",            [("5211",250000,0),("773",0,250000)]),
 ("2026-06-10","Produit HAO",                  [("5211",500000,0),("841",0,500000)]),
 ("2026-06-12","Charge HAO",                   [("812",300000,0),("5211",0,300000)]),
 ("2026-12-31","Impot sur le resultat",        [("8911",1200000,0),("441",0,1200000)]),
]
created=[]
for d,t,l in plan:
    n=je(d,t,l)
    if n: created.append(n)
frappe.db.commit()
print("CREATED", len(created))
if missing: print("MISSING", sorted(missing))
