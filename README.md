# EquiMed

A web-based ERP for **medical-equipment distributors in Cameroon**. It gives
operations staff a clean UI and API for customers, suppliers, products,
inventory, sales, purchases, equipment and maintenance, and turns those into
accounting reports — ledgers, cash/bank books, income statement, balance sheet —
that export as signed PDFs.

It runs on top of **ERPNext** (which stores the accounting, stock and master
data) and is tuned for a Cameroon SME: **XAF** currency and the **SYSCOHADA**
chart of accounts. Everything runs in Docker.

---

## Get it running

You need **Docker** and **Docker Compose** (and ~4 GB free RAM for ERPNext).

```bash
git clone <this-repo-url> equimed
cd equimed
cp .env.example .env            # optional: edit secrets before first run
docker compose up -d --build
```

The **first boot builds the ERPNext site**, which takes a few minutes. Watch it
finish, then you're ready:

```bash
docker compose logs -f erpnext-create-site     # wait until it exits successfully
```

Open **http://localhost** and sign in:

| | |
| --- | --- |
| **Email** | `admin@equimed.cm` |
| **Password** | `admin12345` |

(The defaults come from `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` in `.env`.)

**Optional — load demo data** (customers, products, sales, etc.):

```bash
docker compose cp scripts/seed_erpnext.py erpnext-backend:/tmp/seed.py
echo "exec(open('/tmp/seed.py').read(), {})" | \
  docker compose exec -T erpnext-backend bench --site equimed.local console
# it prints an ERPNEXT_API_KEY / SECRET — put them in .env, then:
docker compose up -d backend
```

After changing code, rebuild the affected service(s):

```bash
docker compose up -d --build backend frontend
```

### Where things live

| What | URL |
| --- | --- |
| **The app** | http://localhost |
| API + interactive docs | http://localhost/api/docs |
| ERPNext admin desk | http://localhost:8080 |

> Heads-up: **http://localhost is the app; :8080 is the ERPNext admin desk** —
> not the app. That trips people up.

For HTTPS, backups and production hardening, see
**[docs/deployment.md](docs/deployment.md)**.

---

## What's inside

- **Operations** — customers, suppliers, products, inventory (warehouses,
  batches, stock movements), equipment (serial numbers) and maintenance visits,
  all with full-page create/edit forms.
- **Transactions** — sales invoices and purchase bills entered ERPNext-style
  (line-item grid, live totals) and posted straight to the ledger; record
  receipts and payments.
- **Accounting** — aged receivable/payable ledgers, cash book, bank book,
  income statement and balance sheet, read back from the ERPNext general ledger.
- **Reports** — one-click **branded, digitally-signed (PAdES) PDF** export of any
  report, with editable company letterhead.
- **Budget** — set monthly targets per category and track them against actuals.
- **First-time setup** — a guided wizard to enter opening balances (bank, open
  invoices/bills, stock, loans) when a business starts on EquiMed.
- **Platform** — JWT auth, six roles with per-endpoint access control, a KPI
  dashboard, and French/English UI.
- **White-label** — product name, logos, theme colours and dashboard composition
  are all per-customer settings, not code.
- **Multi-tenant (optional)** — the same build runs as a self-hosted single-tenant
  install *or* as a shared SaaS plane with a control plane for provisioning,
  suspension, plans and billing-driven feature gating.

Roles: `Administrator`, `Manager`, `Sales`, `Store Keeper`, `Accountant`,
`Biomedical Engineer`. Finance & reports are limited to Manager/Accountant;
user management to Administrator.

---

## How it fits together

```
Browser → Caddy → Next.js (frontend) → FastAPI (backend) → ERPNext → MariaDB
                                            │                   ↑
                                    SQLite (app data)     Redis (cache/queue)
```

- The frontend never talks to ERPNext directly — only the backend does, through
  a single integration module (`backend/integrations/erpnext.py`).
- App users/auth/branding live in the backend's own small database; all business
  and accounting data lives in ERPNext.

On the SaaS plane a separate **control plane** (`platform/`) owns the tenant
registry and provisioning, and the tenant app resolves which customer a request
belongs to from its hostname.

More detail: **[docs/architecture.md](docs/architecture.md)** and
**[docs/multi-tenancy.md](docs/multi-tenancy.md)**.

---

## Develop locally

```bash
# Backend (backend/)
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest                       # tests run against a fake ERPNext + temp SQLite
uvicorn main:app --reload    # http://localhost:8000

# Frontend (frontend/)
npm install
npm run dev                  # http://localhost:3000 (proxies /api → :8000)
npm run build                # type-check + production build

# Control plane (SaaS plane only)
cd platform/api && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && pytest
uvicorn main:app --reload --port 8100

cd platform/ui && npm install && npm run dev   # http://localhost:3100
```

Running the tests **inside the running backend container**? Point them at a
throwaway DB so they don't hit the live one:

```bash
docker compose exec -e DATABASE_URL="sqlite:////tmp/pytest.db" -T backend \
  sh -c 'rm -f /tmp/pytest.db; python -m pytest -q'
```

---

## Project layout

```
backend/       FastAPI service — api / services / repositories / integrations /
               schemas / models / tenancy / utils, plus tests.
               integrations/erpnext.py is the only module that talks to ERPNext.
frontend/      Next.js 14 (App Router) + Tailwind app — app / components / lib.
platform/api   Control plane API (tenant registry, plans, provisioning, audit).
platform/ui    Operator console — its own palette, its own /papi prefix.
caddy/         Caddyfile (single-tenant) · Caddyfile.saas (shared plane).
scripts/       seed_erpnext.py (demo data), backup.sh (per-site backup).
docs/          api.md · architecture.md · deployment.md · multi-tenancy.md ·
               integrations.md · coding_guidelines.md
docker-compose.yml
```

---

## Docs

- **[docs/api.md](docs/api.md)** — endpoints, roles, payloads
- **[docs/architecture.md](docs/architecture.md)** — layers & ERPNext integration
- **[docs/multi-tenancy.md](docs/multi-tenancy.md)** — tenancy, isolation, control
  plane, white-labelling, and the operational risks that come with them
- **[docs/integrations.md](docs/integrations.md)** — add-on roadmap: e-invoicing,
  mobile money, WhatsApp, payroll — what to build, in what order, and why
- **[docs/deployment.md](docs/deployment.md)** — Compose services, HTTPS, backups
- **[docs/coding_guidelines.md](docs/coding_guidelines.md)** — backend conventions

---

## Good to know

- The PDF signing certificate is **self-signed** — signatures are valid but show
  as "unknown issuer" until the certificate is trusted.
- The backend's own database is **SQLite** by default (fine for a single VPS);
  move to MariaDB + migrations before scaling.
- ERPNext is the source of truth for accounting and stock — the app reads and
  writes it, never the reverse.
