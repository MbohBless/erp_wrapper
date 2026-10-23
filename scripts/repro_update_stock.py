#!/usr/bin/env python3
"""Drive the 'Update stock' checkbox against a real ERPNext and report what moves.

    backend/.venv/bin/python scripts/repro_update_stock.py

Exercises the sales invoice `update_stock` flag end to end through the app's own
API — the same calls the browser makes — and reads the stock level back from
ERPNext between each step. Nothing is asserted about the fake; every number here
came out of a live Bin.

Scenarios, in order:
  1. flag ON,  stock available      — the happy path
  2. flag OFF, stock available      — the control: stock must NOT move
  3. flag ON,  amendment of (1)     — a correction must not double-count
  4. flag ON,  qty exceeds stock    — what the user sees when it cannot post

Read-only against production; this is for the local stack only. It refuses to
run against anything that is not localhost.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
# The production overlay redirects :80 to :443 and Caddy signs `localhost`
# with its own internal CA, so verification is off and redirects are followed.
BASE = "https://localhost/api"

GREEN, RED, YELLOW, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def env_get(key: str) -> str:
    """Read one key from .env. Never source it — sourcing executes it."""
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def ok(m):
    print(f"{GREEN}✓{OFF} {m}")


def bad(m):
    print(f"{RED}✗{OFF} {m}")


def info(m):
    print(f"{DIM}  {m}{OFF}")


class App:
    def __init__(self, token: str) -> None:
        self.c = httpx.Client(
            base_url=BASE,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
            verify=False,
            follow_redirects=True,
        )

    def stock(self, item_code: str) -> float:
        rows = self.c.get("/inventory/stock", params={"item_code": item_code}).json()
        return sum(r["actual_qty"] for r in rows) if rows else 0.0

    def post(self, path: str, payload: dict) -> httpx.Response:
        return self.c.post(path, json=payload)

    def put(self, path: str, payload: dict) -> httpx.Response:
        return self.c.put(path, json=payload)


def login() -> str:
    email, password = env_get("FIRST_ADMIN_EMAIL"), env_get("FIRST_ADMIN_PASSWORD")
    r = httpx.post(
        f"{BASE}/auth/login",
        data={"username": email, "password": password},
        timeout=60,
        verify=False,
        follow_redirects=True,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> int:
    if "localhost" not in BASE:
        bad("this script is for the local stack only")
        return 2

    app = App(login())
    ok(f"signed in as {env_get('FIRST_ADMIN_EMAIL')}")

    # ---------------------------------------------------------------- fixtures
    sku = "REPRO-STOCK-01"
    # Leaf nodes only — the reference endpoint already excludes group nodes and
    # disabled records, which is exactly what a transaction needs.
    options = app.c.get("/reference/options").json()
    warehouse = options["warehouses"][0]
    category = options["item_groups"][0]
    info(f"warehouse={warehouse} category={category}")

    if app.c.get(f"/products/{sku}").status_code == 404:
        r = app.post(
            "/products",
            {
                "name": "Repro Stock Widget",
                "sku": sku,
                "category": category,
                "selling_price": 1000,
                "purchase_price": 600,
            },
        )
        if r.status_code >= 400:
            bad(f"could not create product: {r.status_code} {r.text[:300]}")
            return 1
    ok(f"product {sku} ready")

    customer = "Repro Clinic"
    if app.c.get(f"/customers/{customer}").status_code == 404:
        r = app.post("/customers", {"name": customer})
        if r.status_code >= 400:
            bad(f"could not create customer: {r.status_code} {r.text[:300]}")
            return 1
    ok(f"customer {customer} ready")

    r = app.post(
        "/inventory/receive",
        {"warehouse": warehouse, "items": [{"item_code": sku, "qty": 100, "rate": 600}]},
    )
    if r.status_code >= 400:
        bad(f"goods receipt failed: {r.status_code} {r.text[:300]}")
        return 1
    ok(f"received 100 into {warehouse}")

    def invoice(qty: float, update_stock: bool) -> dict:
        return {
            "customer": customer,
            "update_stock": update_stock,
            "items": [{"item_code": sku, "qty": qty, "rate": 1000}],
        }

    failures = 0

    # ------------------------------------------------ 1. flag ON, stock present
    print(f"\n{YELLOW}1. Update stock TICKED, 10 of 100 sold{OFF}")
    before = app.stock(sku)
    r = app.post("/sales", invoice(10, True))
    info(f"POST /sales -> {r.status_code}")
    if r.status_code >= 400:
        bad(f"invoice refused: {r.text[:400]}")
        failures += 1
        first_id = None
    else:
        first_id = r.json()["id"]
        info(f"invoice {first_id}, update_stock={r.json()['update_stock']}")
        after = app.stock(sku)
        info(f"stock {before} -> {after}")
        if after == before - 10:
            ok("stock decreased by 10")
        else:
            bad(f"expected {before - 10}, got {after}  <-- STOCK DID NOT UPDATE")
            failures += 1

    # ------------------------------------------------ 2. flag OFF (the control)
    print(f"\n{YELLOW}2. Update stock UNTICKED, 10 sold{OFF}")
    before = app.stock(sku)
    r = app.post("/sales", invoice(10, False))
    info(f"POST /sales -> {r.status_code}")
    if r.status_code >= 400:
        bad(f"invoice refused: {r.text[:400]}")
        failures += 1
    else:
        after = app.stock(sku)
        info(f"stock {before} -> {after}")
        if after == before:
            ok("stock unchanged, as designed")
        else:
            bad(f"stock moved without the flag: {before} -> {after}")
            failures += 1

    # ------------------------------------------------ 3. amend, flag preserved
    print(f"\n{YELLOW}3. Amend invoice 1 (same qty), flag carried{OFF}")
    if first_id:
        before = app.stock(sku)
        r = app.put(f"/sales/{first_id}", invoice(10, True))
        info(f"PUT /sales/{first_id} -> {r.status_code}")
        if r.status_code >= 400:
            bad(f"amend refused: {r.text[:400]}")
            failures += 1
        else:
            after = app.stock(sku)
            info(f"new id {r.json()['id']}, stock {before} -> {after}")
            if after == before:
                ok("cancel returned 10 and the replacement took 10 back out")
            else:
                bad(f"correction moved stock by {after - before}  <-- INVENTORY DRIFT")
                failures += 1

    # ------------------------------------------------ 4. flag ON, not enough stock
    print(f"\n{YELLOW}4. Update stock TICKED, qty exceeds what is on hand{OFF}")
    before = app.stock(sku)
    r = app.post("/sales", invoice(before + 50, True))
    info(f"POST /sales -> {r.status_code}")
    info(f"body: {r.text[:400]}")
    after = app.stock(sku)
    info(f"stock {before} -> {after}")
    if r.status_code >= 400:
        ok("refused, as it should be")
        drafts = [
            s
            for s in app.c.get("/sales", params={"limit": 100}).json()
            if s.get("status") == "Draft"
        ]
        if drafts:
            bad(f"but it left {len(drafts)} orphaned draft(s): {[d['id'] for d in drafts]}")
            failures += 1
        else:
            ok("and left no orphaned draft")
    else:
        bad("posted an invoice for stock that does not exist")
        failures += 1

    print()
    if failures:
        bad(f"{failures} problem(s) found")
    else:
        ok("all four scenarios behaved as designed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
