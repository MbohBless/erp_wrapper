# EquiMed — Architecture

EquiMed is a medical-equipment distribution platform for a Cameroon SME. It is a
purpose-built UI/API layered **on top of ERPNext**, which remains the system of
record for accounting, stock and master data.

## High-level flow

```
                 ┌────────────┐
 Browser ──HTTP──▶   Caddy    │  (reverse proxy, :80)
                 └─────┬──────┘
        /              │ /api/*                 erp.localhost
        ▼              ▼                              ▼
  ┌───────────┐  ┌───────────┐   ERPNext REST  ┌───────────────┐
  │  Next.js  │  │  FastAPI  │ ───────────────▶│    ERPNext    │
  │ frontend  │  │  backend  │                 │  (Frappe)     │
  └───────────┘  └─────┬─────┘                 └──────┬────────┘
                       │ SQLAlchemy                    │
                       ▼                               ▼
                 ┌───────────┐                   ┌──────────┐   ┌────────┐
                 │  SQLite   │                   │ MariaDB  │   │ Redis  │
                 │(app auth) │                   │(ERPNext) │   │ cache+ │
                 └───────────┘                   └──────────┘   │ queue  │
                                                                └────────┘
```

**Golden rule:** the frontend never talks to ERPNext directly — only FastAPI
does, and only through one module.

## Data ownership

| Concern | Store | Owner |
| --- | --- | --- |
| App users, roles, password hashes, JWT auth | SQLite (`backend-data` volume) | FastAPI |
| Customers, suppliers, products, stock, invoices, equipment, GL | MariaDB | ERPNext |

The two never share a database. FastAPI reads/writes ERPNext business data over
its REST API.

## Backend layers (`backend/`)

A strict layered architecture (enforced by `docs/coding_guidelines.md`):

```
api/            Thin FastAPI routers — no business logic, just DI + RBAC + I/O
services/       Business logic (validation, orchestration, 404/409 mapping)
repositories/   Data access (repository pattern) — DB (users) or ERPNext (rest)
integrations/   erpnext.py — the ONLY module that talks to ERPNext
schemas/        Pydantic v2 request/response models
models/         SQLAlchemy ORM models (users)
utils/          security (JWT/bcrypt), mapping (domain↔ERPNext helpers)
config.py       Pydantic settings   main.py  app factory + router wiring
```

**Request path:** router → `Depends(get_*_service)` → service → repository →
`ERPNextClient` (or SQLAlchemy session). Dependency injection is centralized in
`api/deps.py`; ERPNext-backed services are wired by a small typed factory
(`erpnext_service(build)`), users/auth use two-layer DI.

### The ERPNext integration layer (`integrations/erpnext.py`)

- `ERPNextClient` — transport: generic DocType CRUD (`list/get/create/update/
  delete_document`), `submit_document`, `run_report`; maps failures to
  `ERPNextError` / `ERPNextNotFound`.
- Domain wrappers — `create_customer`, `create_invoice`, `create_purchase`
  (post + submit), `get_balance_sheet`, `get_income_statement`.
- Every repository maps a domain object to ERPNext fields via
  `utils/mapping.to_erpnext(...)`; non-native fields use `custom_*` Custom Fields.

### Module → ERPNext DocType map

| Module | DocType | Notes |
| --- | --- | --- |
| Customers / Suppliers / Products | Customer / Supplier / Item | CRUD proxy |
| Inventory | Warehouse, Batch, Bin, Stock Entry | stock = Bin; movements submit a Stock Entry |
| Sales / Purchases | Sales Invoice / Purchase Invoice | create posts + submits |
| Equipment | Serial No | + install action |
| Maintenance | Maintenance Visit | + complete/sign action |
| Finance / Dashboard | invoices, payments, bins, query reports | aggregation only |

## Authentication & RBAC

- JWT (HS256) issued by FastAPI; bcrypt password hashing.
- 6 roles; `require_roles(...)` dependency guards each route; **Administrator is
  always allowed**. An initial admin is seeded on first boot.
- See [api.md](api.md) for per-endpoint view/manage matrices.

## Frontend (`frontend/`)

- **Next.js 14** (App Router) + **TypeScript** + **Tailwind CSS**, implementing
  the imported **EquiMed "Distribution Suite"** design (blueprint cards, Barlow
  fonts, light/dark themes).
- **React Query** for server state; a shared `lib/http.ts` client (typed
  `api.get/post/put/del`, auth headers, error handling).
- Shared UI primitives in `components/ui/` (`Drawer`, `Modal`, `StatusTag`,
  `RowActions`, `TableSkeleton`, `useDebounced`); an `AppShell` (sidebar + header
  + auth gate) wraps every page.
- Pages: dashboard, sales, purchases, customers, suppliers, products, inventory,
  equipment, maintenance, finance, reports, settings.

## Technology stack

FastAPI · SQLAlchemy 2 · Pydantic v2 · PyJWT · passlib/bcrypt · httpx ·
Next.js 14 · React 18 · Tailwind · @tanstack/react-query · ERPNext/Frappe ·
MariaDB · Redis · Caddy · Docker Compose.

## Testing

`backend/tests/` — 14 pytest modules, 105 tests. ERPNext is replaced by an
in-memory `FakeERPNextClient` (dependency-overridden), and the app-auth DB uses
a temp SQLite; the suite covers CRUD, RBAC, domain actions (install, complete,
receive/issue), search/filter, and the integration wrappers — no live ERPNext
needed. The frontend is verified via `next build`.
