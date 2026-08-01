# EquiMed — Architecture

EquiMed is a medical-equipment distribution platform for a Cameroon SME. It is a
purpose-built UI/API layered **on top of ERPNext**, which remains the system of
record for accounting, stock and master data.

## High-level flow

```
                 ┌────────────┐
 Browser ──HTTP──▶   Caddy    │  (reverse proxy, :80/:443)
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
                 │(app-owned)│                   │(ERPNext) │   │ cache+ │
                 └───────────┘                   └──────────┘   │ queue  │
                                                                └────────┘
```

**Golden rule:** the frontend never talks to ERPNext directly — only FastAPI
does, and only through one module.

On the shared SaaS plane (`TENANCY_MODE=multi`, `--profile saas`) the same
services are joined by a control plane on its own hostname:

```
  console.<domain>          <tenant>.<domain>  /  customer's own domain
        │                              │
        ▼                              ▼
  ┌───────────┐               ┌────────────────┐
  │ platform  │               │ frontend +     │  tenant resolved from Host
  │    UI     │               │ backend        │──┐
  └─────┬─────┘               └───────┬────────┘  │ ERPNext site per tenant
        │ /papi                       │           ▼
  ┌─────▼──────┐   resolve(host)      │      ┌──────────┐
  │ platform   │◀─────────────────────┘      │  Frappe  │
  │    API     │   bootstrap/purge           │  bench   │
  └─────┬──────┘─────────────────────▶       │(N sites) │
        ▼                                    └──────────┘
  ┌───────────┐
  │  SQLite   │  tenant registry, plans, operators, audit
  └───────────┘
```

## Data ownership

| Concern | Store | Owner |
| --- | --- | --- |
| App users, roles, password hashes, JWT auth | SQLite (`backend-data` volume) | FastAPI |
| Company profile, branding, dashboard layout, budgets, books-setup state | SQLite (same) | FastAPI |
| Customers, suppliers, products, stock, invoices, equipment, GL | MariaDB | ERPNext |
| Tenant registry, plans, platform operators, audit log | SQLite (`platform-data` volume) | Control plane |

They never share a database. FastAPI reads/writes ERPNext business data over its
REST API. Every app-owned table carries a `tenant_id`; ERPNext isolation is at
the site/database level.

## Backend layers (`backend/`)

A strict layered architecture (enforced by `docs/coding_guidelines.md`):

```
api/            Thin FastAPI routers — no business logic, just DI + RBAC + I/O
services/       Business logic (validation, orchestration, 404/409 mapping)
repositories/   Data access (repository pattern) — DB (app-owned) or ERPNext
integrations/   The ONLY modules allowed to make outbound HTTP calls:
                  erpnext.py       — the only module that talks to ERPNext
                  control_plane.py — tenant resolution (multi-tenant mode only)
schemas/        Pydantic v2 request/response models
models/         SQLAlchemy ORM models (users, company profile, branding, budget)
tenancy/        Cross-cutting: tenant context, resolution, request binding
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
  always allowed**. An initial admin is seeded on first boot (single-tenant only).
- Tokens carry a `tid` (tenant) claim, checked against the request's resolved
  tenant — see [multi-tenancy.md](multi-tenancy.md).
- `require_feature(...)` additionally gates routes on the tenant's plan, returning
  **402** rather than 403 so "your plan cannot" is distinguishable from "you cannot".
- See [api.md](api.md) for per-endpoint view/manage matrices.

## Tenancy

The same codebase ships as a **self-hosted single-tenant** product and as a
**shared SaaS plane**, selected by `TENANCY_MODE`. A cross-cutting `tenancy/`
package sits beside the layering (like `utils/`):

```
tenancy/context.py     TenantContext + the single ContextVar accessor
tenancy/resolver.py    StaticTenantResolver (single) | ControlPlaneResolver (multi)
tenancy/middleware.py  Binds a tenant to every request before CORS/auth/DB
```

`get_erpnext_client()` builds its client from the *request's* tenant rather than
from global settings — that one function is what makes every ERPNext-backed
service multi-tenant. App-owned tables carry `tenant_id` (`models/mixins.py`)
and their repositories are constructed per tenant.

On the SaaS plane a separate **control plane** service (`platform/`) owns the
tenant registry, plans, provisioning and suspension. It has its own database and
its own signing key, and the tenant app reaches it only through
`integrations/control_plane.py`. Full design, threat model and operational
risks: **[multi-tenancy.md](multi-tenancy.md)**.

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

`backend/tests/` — 16 pytest modules, 150 tests. ERPNext is replaced by an
in-memory `FakeERPNextClient` (dependency-overridden), and the app-auth DB uses
a temp SQLite; the suite covers CRUD, RBAC, domain actions (install, complete,
receive/issue), search/filter, and the integration wrappers — no live ERPNext
needed.

`tests/test_tenancy.py` and `tests/test_branding.py` are the isolation and
input-validation suites: cross-tenant token replay, per-tenant data scoping,
suspension enforcement, and the CSS-injection payloads branding must reject.

`platform/api/tests/` — 34 tests covering the tenant lifecycle, operator RBAC,
secret encryption at rest and TLS authorisation.

Both frontends are verified via `next build`.
