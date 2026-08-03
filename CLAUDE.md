# CLAUDE.md

Guidance for working in this repository. **Always consult `/docs` before making
changes** and keep it up to date when behaviour changes.

## What this is

EquiMed — a medical-equipment distribution platform for a Cameroon SME. A
Next.js + FastAPI UI/API layered on top of **ERPNext** (the system of record for
accounting, stock and master data). Runs on Docker Compose.

It ships in two modes from one codebase, selected by `TENANCY_MODE`:
**`single`** (self-hosted, one implicit tenant, no control plane — the default)
and **`multi`** (shared SaaS plane, tenant resolved per request from the `Host`
header, with a separate control plane in `platform/`).

## Documentation — read these first (`/docs`)

| When you need… | Read |
| --- | --- |
| Endpoints, payloads, per-role RBAC, error model | [docs/api.md](docs/api.md) |
| Layers, data ownership, ERPNext integration, stack | [docs/architecture.md](docs/architecture.md) |
| Docker Compose, config, HTTPS, backups, ops | [docs/deployment.md](docs/deployment.md) |
| Backend layering/style rules (authoritative) | [docs/coding_guidelines.md](docs/coding_guidelines.md) |
| Tenancy, isolation, control plane, white-labelling | [docs/multi-tenancy.md](docs/multi-tenancy.md) |
| Mobile money: providers, webhooks, reconciliation | [docs/payments.md](docs/payments.md) |
| Add-on roadmap, payment/tax/messaging integrations | [docs/integrations.md](docs/integrations.md) |
| Original V1 product brief | [docs/system-design.md](docs/system-design.md) |

The [README.md](README.md) is the top-level index and links to all of the above.
**When you change routes, RBAC, config, or architecture, update the matching doc
in `/docs` (and the README if the index changes) in the same change.**

## Architecture rules (do not violate)

- **ERPNext choke point:** only `backend/integrations/erpnext.py` may talk to
  ERPNext. Everything else goes through `ERPNextClient` / the domain wrappers.
  The frontend must never call ERPNext directly.
- **Outbound HTTP is confined to `integrations/`.** Today that is `erpnext.py`,
  `control_plane.py` and `integrations/payments/*` — no `httpx` anywhere else.
- **Payments: never hold customer funds.** Tenants supply their own merchant
  credentials and money settles directly to them. Holding float would make this
  a licensed money-transmission business under CEMAC rules.
- **Payments: a webhook is a hint, never truth.** Nothing reaches the ledger on
  the strength of a callback — always re-confirm via the provider's status API.
  `tests/test_payment_gateway.py::test_a_lying_webhook_cannot_mark_an_invoice_paid`
  pins this; a failure there is a security incident.
- **Strict layers:** `api/` (thin routers, no business logic) → `services/`
  (business logic) → `repositories/` (data access, repository pattern) →
  `integrations/erpnext.py` or SQLAlchemy. Pydantic v2 in `schemas/`.
- **DI:** wire services in `api/deps.py` (ERPNext services via the
  `erpnext_service(build)` factory; users/auth via two-layer DI). Guard routes
  with `require_roles(...)`; **Administrator is always allowed**. Plan-gated
  routes add `require_feature(...)` (returns 402, not 403).
- **Tenant isolation (do not weaken):**
  - Read the tenant only via `tenancy.current_tenant()` — never the ContextVar.
  - Every app-owned table uses the `TenantScoped` mixin, and its repository is
    constructed for one tenant. No repository may expose an unscoped query.
    Writes *stamp* `tenant_id`; they never trust it from a payload.
  - Access tokens carry a `tid` claim, checked in `get_current_user`.
  - `backend/tests/test_tenancy.py` is the isolation suite. A failure there is a
    security incident, not a bug. Add a cross-tenant test with any new scoped table.
- **Tenant branding is untrusted input.** Theme values are rendered into a
  `<style>` tag; `schemas/branding.py` rejects (never sanitises) anything outside
  the token allowlist / hex-colour / safe-font / `data:image` rules.
- **Data ownership:** app users, auth, branding, budgets live in FastAPI's own DB
  (SQLite by default); all business data lives in ERPNext/MariaDB; the tenant
  registry lives in the control plane's own DB. Never mix them.
- **Control plane separation:** `platform/api` has its own DB, its own signing
  key and its own operator accounts. It is never a role inside the tenant app,
  and the two services talk only over `/internal` with a shared secret.
- **ERPNext field mapping:** use `utils/mapping.to_erpnext(...)`; non-native
  attributes map to `custom_*` Custom Fields (documented in `docs/api.md`).

## Frontend conventions

- Next.js 14 App Router + TypeScript + **Tailwind** (EquiMed design tokens in
  `app/globals.css`). Use the shared primitives in `components/ui/`
  (`Drawer`, `Modal`, `StatusTag`, `RowActions`, `TableSkeleton`, `useDebounced`)
  and the `lib/http.ts` `api` client — don't re-implement fetch/handlers or
  status/skeleton/debounce helpers. Pages are wrapped in `AppShell`.
- **No hardcoded brand strings.** Use `useAppName()` / `useBranding()` — the
  product name, logo and tagline are per-tenant. The ERPNext *Company* name is
  business data: use `useCompanyName()`, never the app name.
- The dashboard is composed from `TenantBranding.dashboard` via
  `components/dashboard/WidgetGrid.tsx`. Adding a panel = a new id in
  `schemas/branding.py`, a case in `WidgetGrid`, a label in `lib/dashboard.ts`.
- `platform/ui` is a **separate** Next.js app with its own dark palette and a
  `/papi` prefix, so the operator console is never mistaken for a workspace.

## Roles

Administrator, Manager, Sales, Store Keeper, Accountant, Biomedical Engineer.
See the RBAC matrix in [docs/api.md](docs/api.md).

## Commands

```bash
# Backend (backend/)
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
pytest                        # 150 tests; ERPNext faked, temp SQLite — no live ERPNext
uvicorn main:app --reload     # dev server on :8000

# Frontend (frontend/)
npm install
npm run dev                   # :3000
npm run build                 # type-check + production build (use this to verify)

# Control plane (platform/api/ and platform/ui/) — SaaS plane only
cd platform/api && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && pytest    # 34 tests
uvicorn main:app --reload --port 8100
cd platform/ui && npm install && npm run dev # :3100

# Full stack
docker compose up -d --build                 # single-tenant
docker compose --profile saas up -d --build  # SaaS plane (see docs/deployment.md)
```

## Expectations

- Add/adjust tests for backend changes; run `pytest` in **both** `backend/` and
  `platform/api/` (must stay green).
- Verify frontend changes with `npm run build` in **both** `frontend/` and
  `platform/ui/`.
- Don't add business logic to routers; don't fabricate ERPNext data.
- Don't hardcode "EquiMed" in user-facing frontend copy — it is white-labelled.
- Keep `/docs` accurate — it is the source of truth for this project.
