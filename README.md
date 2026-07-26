# EquiMed

A lightweight, web-based ERP for **medical-equipment distributors** in Cameroon.
It gives operations staff a clean, purpose-built UI and API for customers,
suppliers, products, inventory, sales, purchases, equipment and maintenance —
while delegating **accounting, stock and master data to ERPNext** (the system of
record). On top of that ledger it produces aged receivable/payable ledgers, a
cash book, a bank book, an income statement and a balance sheet, and exports any
of them as a **branded, digitally-signed PDF**.

> **This is not a generic ERP.** It is a medical-distribution management platform
> layered on ERPNext, tuned for a Cameroon SME: **XAF** currency, **SYSCOHADA**
> chart of accounts, French-language accounts, and a document-entry experience
> modelled on ERPNext itself.

---

## Table of contents

- [What you can do](#what-you-can-do)
- [The accounting & reporting pipeline](#the-accounting--reporting-pipeline)
- [Document entry (ERPNext-style)](#document-entry-erpnext-style)
- [Reporting & signed PDFs](#reporting--signed-pdfs)
- [Architecture at a glance](#architecture-at-a-glance)
- [Modules & routes](#modules--routes)
- [Roles & access](#roles--access)
- [Quick start (Docker)](#quick-start-docker)
- [Local development](#local-development)
- [Repository layout](#repository-layout)
- [Tech stack](#tech-stack)
- [Documentation](#documentation)
- [Status & known follow-ups](#status--known-follow-ups)

---

## What you can do

**Master data & operations**

- **Customers / Suppliers** — full CRM records (contacts, tax IDs, groups,
  territory, lead time) created and edited on full-page forms.
- **Products (Items)** — catalogue with SKU, category, unit, selling/purchase
  price, barcode, manufacturer.
- **Inventory** — warehouses, batches (with expiry/manufacturing dates), live
  stock levels per item/warehouse, and **goods receipt / issue** stock entries.
- **Equipment (Serial No)** — register serialised units, installation and
  warranty dates, status lifecycle, customer/site assignment.
- **Maintenance (Maintenance Visit)** — service tickets with engineer, visit
  date, status, description and parts used.

**Transactions**

- **Sales invoices** and **purchase bills** entered on full ERPNext-style
  documents (line-item grid, live totals, tax template, update-stock, remarks),
  **posted and submitted to the ERPNext ledger** automatically.
- **Payments** — record a receipt against an invoice or a payment against a
  bill; the app creates and submits the matching ERPNext **Payment Entry**.

**Accounting & finance** (read back from the general ledger)

- **Receivable ledger** and **Payable ledger** with aging buckets
  (Current / 1–30 / 31–60 / 61–90 / 90+).
- **Cash book** and **Bank book** with opening/closing balances and running
  balance per entry.
- **Income statement** and **Balance sheet** for a fiscal year or date range.

**Reporting**

- One-click **branded, cryptographically-signed (PAdES) PDF** export of any
  ledger, book, stock report or financial statement.
- Editable **company branding** (letterhead, logo, legal identifiers,
  signatory) that drives every generated PDF.

**Platform**

- JWT authentication, six roles with per-endpoint RBAC (Administrator always
  allowed), and in-app **user & role management**.
- Dashboard with revenue, outstanding customers/suppliers, inventory value and
  low-stock KPIs plus recent activity.

---

## The accounting & reporting pipeline

Every operational input flows into ERPNext's double-entry ledger, and the
finance views/statements are computed **back out of that same ledger** — so the
statements always reflect the transactions:

```
Invoices ─┐
Sales     ├─ posted & submitted ─▶  ERPNext GL Entries  ─▶  Receivable / Payable ledgers (aged)
Purchases │      (SYSCOHADA)              │                  Cash book / Bank book (running balance)
Payments ─┘                              │
Stock movements ─▶ Bin / Stock Ledger ───┘                  Income statement  ┐
                                                            Balance sheet     ├─▶  Signed PDF export
                                                                              ┘
```

| Output | UI | API | Source |
| --- | --- | --- | --- |
| Invoices | Sales → New invoice | `POST /api/sales` | ERPNext `Sales Invoice` (submitted) |
| Sales records | `/sales` | `GET /api/sales` | ERPNext `Sales Invoice` |
| Purchase records | `/purchases` | `GET /api/purchases` | ERPNext `Purchase Invoice` |
| Receivable ledger | Finance → Receivables | `GET /api/finance/receivable` | GL / outstanding invoices, aged |
| Payable ledger | Finance → Payables | `GET /api/finance/payable` | GL / outstanding bills, aged |
| Inventory / stock | `/inventory` | `GET /api/inventory/stock` | ERPNext `Bin` |
| Cash book | Finance → Cash book | `GET /api/finance/cash-book` | GL Entries (Caisse accounts) |
| Bank book | Finance → Bank book | `GET /api/finance/bank-book` | GL Entries (Bank accounts) |
| Income statement | Reports | `GET /api/finance/reports/income-statement` | ERPNext P&L report |
| Balance sheet | Reports | `GET /api/finance/reports/balance-sheet` | ERPNext Balance Sheet report |

> Bank/cash entries appear once payments are recorded through the app (which
> creates the Payment Entries). Statement accuracy depends on the ERPNext
> company having its accounting defaults set (income/expense/round-off/stock
> accounts) — already configured for the seeded **EquiMed** company, FY 2026.

---

## Document entry (ERPNext-style)

Sales, purchases and all Operations/Relationships records are entered on
**full-page, tabbed documents** rather than cramped modals, mirroring the
ERPNext desk experience:

- A shared shell (`components/ui/DocFormShell.tsx`) renders the header
  (back, breadcrumb, title, *Not saved* / *Editing* status pill, Cancel/Save)
  and a tab strip; each module supplies its fields.
- **Sales invoice / purchase bill / stock entry** documents include an editable
  **line-item grid** (item picker with auto-filled rate, quantity, batch,
  amount, live totals), plus a *More info* tab (posting/due dates, remarks,
  tax template, update-stock).
- Create and edit share the same form via `/{module}/new` and
  `/{module}/[id]/edit` routes.
- Read-only **detail panels** slide in as full-height side drawers
  (portalled to `body`, so they anchor to the viewport edge-to-edge).

UI is **Material 3**-styled (outlined fields, Roboto, stadium buttons) over the
EquiMed "blueprint" design tokens in `app/globals.css`.

---

## Reporting & signed PDFs

The Reports page is a two-pane selector + inline preview. Each report exports a
professional PDF that is **cryptographically signed**:

- **Rendering** — a branded A4 letterhead (logo, legal name, address, RC/NIU,
  tagline, accent rule), a styled data table with totals, an authorised-
  signature block and `Page X of Y` footer (reportlab).
- **Signing** — an embedded **PAdES** signature (pyHanko). A self-signed
  certificate is auto-provisioned once into the persistent `/app/data/signing`
  volume; any modification after signing invalidates the signature. (Self-signed
  ⇒ valid signature, "unknown issuer" until the certificate is trusted.)
- **Branding** — an editable singleton profile stored in the app DB, managed in
  **Settings → Company & branding** (`GET/PUT /api/settings/company-profile`),
  including a logo uploaded as a data-URI.

Reports: `receivables`, `payables`, `current-stock`, `low-stock`,
`income-statement`, `balance-sheet` — `GET /api/reports/{key}/pdf`.

---

## Architecture at a glance

```
Users → Caddy → Next.js frontend → FastAPI backend → ERPNext → MariaDB
                                         │                        ↑
                                    SQLite (app auth              Redis (cache
                                    + company profile)             + queue)
```

- **ERPNext is the single choke point** — only `backend/integrations/erpnext.py`
  talks to ERPNext (or uses `httpx`). The frontend never calls ERPNext directly.
- **Strict layers** — `api/` (thin routers) → `services/` (business logic) →
  `repositories/` (data access) → `integrations/erpnext.py` or SQLAlchemy.
  Pydantic v2 schemas in `schemas/`.
- **Data ownership** — app users/auth **and** the branding profile live in
  FastAPI's own DB (SQLite by default); all business/accounting data lives in
  ERPNext/MariaDB. The two are never mixed.

Full detail: **[docs/architecture.md](docs/architecture.md)** ·
**[docs/coding_guidelines.md](docs/coding_guidelines.md)**.

---

## Modules & routes

| Area | List | Create / edit | Backing ERPNext DocType |
| --- | --- | --- | --- |
| Dashboard | `/dashboard` | — | invoices, payments, bins (aggregated) |
| Sales | `/sales` | `/sales/new` | Sales Invoice |
| Purchases | `/purchases` | `/purchases/new` | Purchase Invoice |
| Products | `/products` | `/products/new`, `/products/[id]/edit` | Item |
| Inventory | `/inventory` | `/inventory/new?mode=receive\|issue` | Warehouse, Batch, Bin, Stock Entry |
| Equipment | `/equipment` | `/equipment/new`, `/equipment/[id]/edit` | Serial No |
| Maintenance | `/maintenance` | `/maintenance/new`, `/maintenance/[id]/edit` | Maintenance Visit |
| Customers | `/customers` | `/customers/new`, `/customers/[id]/edit` | Customer |
| Suppliers | `/suppliers` | `/suppliers/new`, `/suppliers/[id]/edit` | Supplier |
| Finance | `/finance` | — | GL: receivables, payables, cash/bank book, statements |
| Reports | `/reports` | — | signed PDF exports of stock & finance reports |
| Settings | `/settings` | — | profile, **company & branding**, **users & roles**, theme |

Every endpoint, payload and the full RBAC matrix: **[docs/api.md](docs/api.md)**.

---

## Roles & access

`Administrator` (always allowed), `Manager`, `Sales`, `Store Keeper`,
`Accountant`, `Biomedical Engineer`. Routes are guarded with
`require_roles(...)`. Highlights:

- **Finance & Reports** — Manager, Accountant.
- **Company-profile edit** — Manager, Accountant (read: any authenticated user).
- **User management** — Administrator only.

---

## Quick start (Docker)

```bash
cp .env.example .env          # set JWT_SECRET_KEY, admin + DB passwords, etc.
docker compose up -d --build
docker compose logs -f erpnext-create-site   # first boot provisions the ERPNext site
```

| What | URL | Notes |
| --- | --- | --- |
| **App** | `http://localhost/` | Caddy serves the app on **port 80** |
| API + Swagger | `http://localhost/api/docs` | FastAPI (prefix `/api`) |
| **ERPNext desk** | `http://localhost:8080/` | ERPNext admin UI — **not** the app |

Sign in with `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` (default
`admin@equimed.cm` / `admin12345`). The admin account and the default company
branding profile are seeded on first backend start.

> **`http://localhost` is the app; `:8080` is the ERPNext desk** — a common
> mix-up. Login is OAuth2 form-encoded (`POST /api/auth/login`).

Rebuild after code changes:

```bash
docker compose up -d --build backend frontend
```

Deployment, HTTPS, backups and production hardening:
**[docs/deployment.md](docs/deployment.md)**.

---

## Local development

```bash
# Backend  (backend/)
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest                        # 111 tests (ERPNext faked, temp SQLite — no live ERPNext)
uvicorn main:app --reload     # http://localhost:8000

# Frontend  (frontend/)
npm install
npm run dev                   # http://localhost:3000  (proxies /api → :8000 in dev)
npm run build                 # type-check + production build (use this to verify)
```

**Running tests inside the live backend container?** The container exports
`DATABASE_URL=/app/data/app.db`, which overrides the test config and makes tests
hit the real DB (spurious "email already registered" failures). Force a fresh DB:

```bash
docker compose exec -e DATABASE_URL="sqlite:////tmp/pytest-fresh.db" -T backend \
  sh -c 'rm -f /tmp/pytest-fresh.db; python -m pytest -q'
```

---

## Repository layout

```
backend/
  api/            thin routers (auth, users, customers, suppliers, products,
                  inventory, sales, purchases, equipment, maintenance, finance,
                  payments, dashboard, settings, reports, health)
  services/       business logic (incl. report_service, company_service)
  repositories/   data access (ERPNext- or SQLAlchemy-backed)
  integrations/   erpnext.py — the ONLY module that talks to ERPNext
  schemas/        Pydantic v2 models
  models/         SQLAlchemy models (User, CompanyProfile)
  utils/          pdf_report.py (reportlab), pdf_signing.py (pyHanko), mapping…
  tests/          111 pytest tests (ERPNext faked)
frontend/
  app/            Next.js 14 App Router pages (list + /new + /[id]/edit routes)
  components/     ui/ primitives (DocFormShell, Drawer, Modal, …) + per-module
  lib/            http client, per-module fetchers, reports.ts, company.ts
caddy/            Caddyfile (public reverse proxy: app on :80, ERPNext on :8080)
scripts/          seed_erpnext.py (demo data) · backup.sh (nightly backup)
docs/             api.md · architecture.md · deployment.md · coding_guidelines.md
                  · system-design.md
docker-compose.yml
```

---

## Tech stack

- **Frontend** — Next.js 14 (App Router), TypeScript, Tailwind CSS,
  @tanstack/react-query, Material 3 styling + Roboto.
- **Backend** — FastAPI, Pydantic v2, SQLAlchemy 2, PyJWT, passlib/bcrypt,
  httpx; reportlab + pyHanko + Pillow for signed PDF reports.
- **System of record** — ERPNext / Frappe on MariaDB, Redis (cache + queue).
- **Infra** — Docker Compose, Caddy reverse proxy (auto-HTTPS ready).

---

## Documentation

- **[docs/api.md](docs/api.md)** — every endpoint, RBAC matrix, payloads, error model
- **[docs/architecture.md](docs/architecture.md)** — layers, data ownership, ERPNext integration, stack
- **[docs/deployment.md](docs/deployment.md)** — Docker Compose services, config, HTTPS, backups
- **[docs/coding_guidelines.md](docs/coding_guidelines.md)** — authoritative backend layering/style rules
- **[docs/system-design.md](docs/system-design.md)** — the original V1 design brief

When routes, RBAC, config or architecture change, update the matching file in
`/docs` (and this README if the index changes) in the same commit.

---

## Status & known follow-ups

All modules have working, tested backends (**111 pytest tests, green**) and
EquiMed-styled frontend pages; the full stack runs under Docker Compose.

- **Signing certificate is self-signed** — signatures are cryptographically
  valid but show "unknown issuer" until the certificate is trusted; wire in a
  real CA/timestamp authority for externally-trusted signatures.
- **App-auth DB is SQLite** — plan a MariaDB + Alembic migration before
  production; startup currently uses `create_all` (no migrations yet).
- **ERPNext Custom Fields** the modules rely on must exist in the target
  instance — created by `scripts/seed_erpnext.py` (see [docs/api.md](docs/api.md)).
- **No in-app journal-entry screen** yet — cash/bank movements flow in via the
  app's payment/stock actions or directly in the ERPNext desk.
