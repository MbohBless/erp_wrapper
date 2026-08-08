#!/usr/bin/env python3
"""Seed a demonstration dataset: users, catalogue, stock, invoices, payments.

    python3 scripts/seed_demo.py --base https://app.example.com/api
    python3 scripts/seed_demo.py --dry-run          # show what it would create

**For demos and evaluation only.** It writes through the public API, so every
document goes through the same validation, RBAC and ERPNext mapping as real use —
nothing is injected into the database behind the application's back.

Two safety properties, because this points at a live host:

  1. It refuses to run if the instance already holds business documents. Seeding
     on top of a customer's real ledger is not recoverable by deleting rows —
     stock and GL entries fan out across doctypes.
  2. Everything it creates is tagged (see ``TAG``), so it can be told apart
     later. That is for auditing, not for cleanup: the supported way back to a
     clean instance is restoring the pre-seed snapshot, because ERPNext
     submitted documents cannot simply be deleted.

Reset afterwards with:

    ./scripts/restore.sh pristine-preseed.tar.gz.enc
"""

from __future__ import annotations

import argparse
import json
import random
import secrets
import string
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

TAG = "DEMO"

# Cloudflare answers 403 to urllib's default headers.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# --- the dataset ----------------------------------------------------------
# A Cameroonian medical-equipment distributor: capital equipment sold to
# hospitals and clinics, plus fast-moving consumables. Prices are XAF.

SUPPLIERS = [
    ("Mindray Medical International", "Shenzhen", "sales@mindray-demo.example", 45),
    ("Dräger Medical Africa", "Johannesburg", "afrique@draeger-demo.example", 60),
    ("B. Braun Afrique Centrale", "Douala", "contact@bbraun-demo.example", 21),
    ("Siemens Healthineers SARL", "Casablanca", "info@siemens-demo.example", 75),
    ("GE HealthCare Distribution", "Nairobi", "orders@gehc-demo.example", 55),
]

# ERPNext rejects a group node as a customer group ("Cannot select a Group type
# Customer Group"), so these name leaf nodes. Government vs Commercial also makes
# the revenue-by-segment chart show more than one slice.
CUSTOMER_GROUPS = {
    "Hôpital Général de Douala": "Government",
    "Hôpital Laquintinie": "Government",
    "Hôpital Régional de Buea": "Government",
    "Centre de Santé de Bafoussam": "Non Profit",
    "Clinique de l'Aéroport": "Commercial",
    "Centre Médical La Cathédrale": "Commercial",
    "Polyclinique Bonanjo": "Commercial",
    "Clinique Saint-Luc": "Commercial",
}

CUSTOMERS = [
    ("Hôpital Général de Douala", "Dr. Ngassa Emmanuel", "+237 233 42 18 90", "Douala, Littoral"),
    ("Hôpital Laquintinie", "Dr. Mbarga Alice", "+237 233 42 33 12", "Douala, Littoral"),
    ("Clinique de l'Aéroport", "M. Tchoua Bernard", "+237 233 39 07 45", "Douala, Littoral"),
    ("Centre Médical La Cathédrale", "Dr. Fotso Marie", "+237 222 23 55 018", "Yaoundé, Centre"),
    ("Polyclinique Bonanjo", "Dr. Essomba Paul", "+237 233 43 21 77", "Douala, Littoral"),
    ("Hôpital Régional de Buea", "Dr. Ashu Grace", "+237 233 32 24 60", "Buea, Sud-Ouest"),
    ("Centre de Santé de Bafoussam", "Mme. Kamga Rose", "+237 233 44 12 09", "Bafoussam, Ouest"),
    ("Clinique Saint-Luc", "Dr. Njoya Idriss", "+237 222 20 88 31", "Yaoundé, Centre"),
]

# (sku, name, manufacturer, purchase_price, selling_price, unit, is_capital)
PRODUCTS = [
    ("EQ-MON-001", "Moniteur patient multiparamétrique 12\"", "Mindray", 1_250_000, 1_850_000, "Nos", True),
    ("EQ-ECH-002", "Échographe portable à sonde convexe", "Mindray", 8_900_000, 12_500_000, "Nos", True),
    ("EQ-DEF-003", "Défibrillateur biphasique avec AED", "Dräger", 3_100_000, 4_450_000, "Nos", True),
    ("EQ-PMP-004", "Pompe à perfusion volumétrique", "B. Braun", 620_000, 940_000, "Nos", True),
    ("EQ-ECG-005", "Électrocardiographe 12 dérivations", "Siemens", 1_450_000, 2_100_000, "Nos", True),
    ("EQ-AUT-006", "Autoclave de table 23 litres", "Dräger", 2_250_000, 3_200_000, "Nos", True),
    ("EQ-OXY-007", "Concentrateur d'oxygène 10 L/min", "GE HealthCare", 890_000, 1_340_000, "Nos", True),
    ("EQ-LAM-008", "Lampe chirurgicale LED sur pied", "Mindray", 1_680_000, 2_400_000, "Nos", True),
    ("EQ-LIT-009", "Lit d'hôpital électrique 3 fonctions", "B. Braun", 740_000, 1_120_000, "Nos", True),
    ("EQ-NEB-010", "Nébuliseur à compresseur", "GE HealthCare", 78_000, 125_000, "Nos", True),
    ("CN-GAN-101", "Gants chirurgicaux stériles T7.5 (boîte de 50)", "B. Braun", 18_500, 29_000, "Box", False),
    ("CN-SER-102", "Seringues 5 ml à usage unique (boîte de 100)", "B. Braun", 9_800, 16_500, "Box", False),
    ("CN-CAT-103", "Cathéters IV 20G (boîte de 50)", "B. Braun", 24_000, 38_000, "Box", False),
    ("CN-COM-104", "Compresses de gaze stériles (paquet de 100)", "Mindray", 6_200, 11_000, "Box", False),
    ("CN-MAS-105", "Masques chirurgicaux type IIR (boîte de 50)", "GE HealthCare", 4_500, 8_200, "Box", False),
]

ROLES = [
    ("Manager", "Nkeng Duval", "duval.nkeng"),
    ("Sales", "Abena Clarisse", "clarisse.abena"),
    ("Store Keeper", "Moussa Ibrahim", "ibrahim.moussa"),
    ("Accountant", "Ewane Sylvie", "sylvie.ewane"),
    ("Biomedical Engineer", "Tabi Georges", "georges.tabi"),
]


class Api:
    def __init__(self, base: str, dry: bool = False) -> None:
        self.base = base.rstrip("/")
        self.token: str | None = None
        self.dry = dry
        self.failures: list[str] = []

    def _call(self, method, path, data=None, form=None, tok=None):
        body, hdr = None, {"User-Agent": UA, "Accept": "application/json"}
        if form is not None:
            body = urllib.parse.urlencode(form).encode()
            hdr["Content-Type"] = "application/x-www-form-urlencoded"
        elif data is not None:
            body = json.dumps(data).encode()
            hdr["Content-Type"] = "application/json"
        t = tok if tok is not None else self.token
        if t:
            hdr["Authorization"] = "Bearer " + t
        req = urllib.request.Request(self.base + path, data=body, headers=hdr, method=method)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            detail = (e.read() or b"").decode()[:300]
            return e.code, {"_error": detail}
        except Exception as e:  # network-level
            return 0, {"_error": str(e)}

    def login(self, email, password):
        st, d = self._call("POST", "/auth/login", form={"username": email, "password": password})
        if st != 200:
            sys.exit(f"login failed for {email}: {st} {d.get('_error','')}")
        self.token = d["access_token"]
        return self.token

    def post(self, path, payload, label):
        if self.dry:
            print(f"  [dry-run] POST {path} {json.dumps(payload, ensure_ascii=False)[:110]}")
            return {"id": "dry-run"}
        st, d = self._call("POST", path, data=payload)
        if st not in (200, 201):
            self.failures.append(f"{label}: HTTP {st} {d.get('_error','')[:160]}")
            return None
        return d

    def get(self, path):
        st, d = self._call("GET", path)
        return d if st == 200 else None


def password_for(slug: str) -> str:
    """Readable but not guessable: two words plus real entropy."""
    alphabet = string.ascii_letters + string.digits
    tail = "".join(secrets.choice(alphabet) for _ in range(10))
    return f"{slug.split('.')[0].capitalize()}-{TAG}-{tail}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://app.qbmedicals.com/api")
    ap.add_argument("--admin-email", required=True)
    ap.add_argument("--admin-password", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="seed even though business documents already exist (dangerous)")
    args = ap.parse_args()

    rnd = random.Random(20260808)  # deterministic: a re-run produces the same figures
    api = Api(args.base, args.dry_run)
    api.login(args.admin_email, args.admin_password)
    print(f"connected to {args.base}")

    # --- safety gate ------------------------------------------------------
    existing_sales = api.get("/sales") or []
    existing_customers = api.get("/customers") or []
    if (existing_sales or existing_customers) and not args.force:
        print()
        print(f"REFUSING TO SEED: this instance already has {len(existing_sales)} invoice(s) "
              f"and {len(existing_customers)} customer(s).")
        print("Seeding onto a real ledger is not undoable by deleting rows. If this is")
        print("genuinely a demo instance, re-run with --force.")
        return 2

    created = {}

    # --- users ------------------------------------------------------------
    print("\n--- users -------------------------------------------------")
    creds = []
    for role, full_name, slug in ROLES:
        email = f"{slug}@qbmedicals.com"
        pw = password_for(slug)
        r = api.post("/users", {"email": email, "full_name": full_name,
                                "role": role, "password": pw}, f"user {email}")
        if r:
            creds.append((role, full_name, email, pw))
            print(f"  {role:22} {email:34} {pw}")
    created["users"] = len(creds)

    # --- suppliers / customers / catalogue --------------------------------
    print("\n--- suppliers ---------------------------------------------")
    for name, city, email, lead in SUPPLIERS:
        r = api.post("/suppliers", {
            "name": name, "supplier_type": "Company", "email": email,
            "address": city, "lead_time_days": lead,
            "supplier_group": "Distributor",
        }, f"supplier {name}")
        if r:
            print(f"  {name}")
    created["suppliers"] = len(SUPPLIERS) - len([f for f in api.failures if f.startswith("supplier")])

    print("\n--- customers ---------------------------------------------")
    customer_ids = []
    for name, contact, phone, addr in CUSTOMERS:
        r = api.post("/customers", {
            "name": name, "customer_type": "Company", "contact_person": contact,
            "phone": phone, "address": addr,
            "customer_group": CUSTOMER_GROUPS.get(name, "Commercial"),
            "territory": "Cameroon",
        }, f"customer {name}")
        if r:
            customer_ids.append(r.get("id") or name)
            print(f"  {name}")
    created["customers"] = len(customer_ids)

    print("\n--- catalogue ---------------------------------------------")
    for sku, name, mfr, buy, sell, unit, _cap in PRODUCTS:
        r = api.post("/products", {
            "sku": sku, "name": name, "manufacturer": mfr,
            "purchase_price": buy, "selling_price": sell, "unit": unit,
        }, f"product {sku}")
        if r:
            print(f"  {sku:12} {name[:46]:46} {sell:>12,} XAF")
    created["products"] = len(PRODUCTS) - len([f for f in api.failures if f.startswith("product")])

    # --- stock ------------------------------------------------------------
    warehouses = api.get("/inventory/warehouses") or []
    leaves = [w["id"] for w in warehouses if not w.get("is_group")]
    # "Stores" is where received goods belong; "Finished Goods" merely happened
    # to sort first.
    wh = next((w for w in leaves if "Stores" in w), None) or (leaves[0] if leaves else None)
    print(f"\n--- goods received into {wh} -------------------------------")
    if wh:
        # Deliberately uneven: a few lines land under the low-stock threshold so
        # that panel has something real to show rather than an empty state.
        lines = []
        for i, (sku, *_rest) in enumerate(PRODUCTS):
            qty = [3, 6, 8][i % 3] if i % 4 == 0 else rnd.choice([25, 40, 60, 120])
            lines.append({"item_code": sku, "qty": qty,
                          "rate": PRODUCTS[i][3]})
        r = api.post("/inventory/receive", {"warehouse": wh, "items": lines}, "goods receipt")
        if r:
            print(f"  received {len(lines)} lines")
            created["stock_lines"] = len(lines)
    else:
        api.failures.append("no non-group warehouse found; stock not seeded")

    # --- purchase invoices ------------------------------------------------
    print("\n--- purchase invoices -------------------------------------")
    n_pi = 0
    for i in range(6):
        sup = SUPPLIERS[i % len(SUPPLIERS)][0]
        picks = rnd.sample(PRODUCTS, k=rnd.randint(1, 3))
        items = [{"item_code": p[0], "qty": rnd.randint(2, 15), "rate": p[3]} for p in picks]
        posting = (date.today() - timedelta(days=rnd.randint(5, 40))).isoformat()
        r = api.post("/purchases", {
            "supplier": sup, "items": items, "posting_date": posting,
            "bill_no": f"{TAG}-PI-{1000 + i}",
        }, f"purchase invoice {i}")
        if r:
            n_pi += 1
            print(f"  {r.get('id','?'):22} {sup[:28]:28} {r.get('grand_total',0):>14,.0f} XAF")
    created["purchase_invoices"] = n_pi

    # --- sales invoices, spread across the trend window -------------------
    print("\n--- sales invoices ----------------------------------------")
    invoices = []
    # The dashboard trend covers 30 days; spreading posting dates across it is
    # what makes the chart a line rather than a single spike.
    for i in range(22):
        cust = customer_ids[i % len(customer_ids)] if customer_ids else CUSTOMERS[0][0]
        picks = rnd.sample(PRODUCTS, k=rnd.randint(1, 3))
        items = [{"item_code": p[0], "qty": rnd.randint(1, 6), "rate": p[4]} for p in picks]
        days_ago = int(i * 29 / 21)
        posting = (date.today() - timedelta(days=days_ago)).isoformat()
        r = api.post("/sales", {
            "customer": cust, "items": items, "posting_date": posting,
            "due_date": (date.today() - timedelta(days=days_ago) + timedelta(days=30)).isoformat(),
            "remarks": f"{TAG} sample order",
        }, f"sales invoice {i}")
        if r:
            invoices.append(r)
            print(f"  {r.get('id','?'):22} {str(cust)[:30]:30} {r.get('grand_total',0):>14,.0f} XAF")
    created["sales_invoices"] = len(invoices)

    # --- payments: settle most, leave some outstanding --------------------
    print("\n--- customer receipts -------------------------------------")
    n_pay = 0
    for inv in invoices:
        # Leaving roughly a third unpaid is what gives the receivables figure and
        # the ageing report something to show.
        if rnd.random() < 0.62 and inv.get("id"):
            mode = rnd.choice(["Cash", "Bank Draft", "Wire Transfer"])
            r = api.post("/payments/receive", {
                "invoice_id": inv["id"],
                "mode_of_payment": mode,
                # Mandatory for anything that lands on a bank account, and
                # harmless for cash.
                "reference_no": f"{TAG}-{rnd.randint(100000, 999999)}",
            }, f"receipt {inv['id']}")
            if r:
                n_pay += 1
    print(f"  recorded {n_pay} receipts; {len(invoices) - n_pay} invoices left outstanding")
    created["receipts"] = n_pay

    # --- equipment + maintenance -----------------------------------------
    print("\n--- installed equipment & maintenance ---------------------")
    n_eq = n_mt = 0
    capital = [p for p in PRODUCTS if p[6]]
    for i in range(10):
        prod = capital[i % len(capital)]
        serial = f"{TAG}-{prod[0].split('-')[1]}-{2600 + i}"
        cust = customer_ids[i % len(customer_ids)] if customer_ids else None
        r = api.post("/equipment", {
            "serial_no": serial, "item_code": prod[0], "customer": cust,
            "status": "Installed" if i % 3 else "In Store",
            "installation_date": (date.today() - timedelta(days=rnd.randint(20, 300))).isoformat(),
            "warranty_expiry_date": (date.today() + timedelta(days=rnd.randint(30, 500))).isoformat(),
        }, f"equipment {serial}")
        if r:
            n_eq += 1
            if i % 2 == 0 and cust:
                m = api.post("/maintenance", {
                    "customer": cust, "equipment": serial,
                    "engineer": "Tabi Georges",
                    "visit_date": (date.today() - timedelta(days=rnd.randint(1, 25))).isoformat(),
                    "description": rnd.choice([
                        "Maintenance préventive trimestrielle",
                        "Calibration des capteurs et remplacement du filtre",
                        "Intervention corrective — alarme intermittente",
                        "Contrôle de sécurité électrique annuel",
                    ]),
                    "status": rnd.choice(["Open", "Scheduled", "In Progress"]),
                }, f"maintenance {serial}")
                if m:
                    n_mt += 1
    created["equipment"] = n_eq
    created["maintenance"] = n_mt
    print(f"  {n_eq} serial numbers, {n_mt} maintenance visits")

    # --- report -----------------------------------------------------------
    print("\n" + "=" * 62)
    print("SEEDED")
    for k, v in created.items():
        print(f"  {k:20} {v}")
    if api.failures:
        print(f"\n{len(api.failures)} FAILURE(S) — reported rather than swallowed:")
        for f in api.failures[:25]:
            print(f"  - {f}")
        if len(api.failures) > 25:
            print(f"  … and {len(api.failures) - 25} more")

    if creds:
        print("\n" + "=" * 62)
        print("DEMO SIGN-IN CREDENTIALS")
        print(f"{'ROLE':22} {'EMAIL':34} PASSWORD")
        for role, _name, email, pw in creds:
            print(f"{role:22} {email:34} {pw}")
        print("\nThese are demo accounts. Delete them before handover, or restore")
        print("the pre-seed snapshot, which removes them along with the data.")

    return 1 if api.failures else 0


if __name__ == "__main__":
    sys.exit(main())
