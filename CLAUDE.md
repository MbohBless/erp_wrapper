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
| Add-on roadmap, payment/tax/messaging integrations | [docs/integrations.md](docs/integrations.md) |
| Original V1 product brief | [docs/system-design.md](docs/system-design.md) |
| Why a thing works the way it does; what was rejected | [docs/decisions.md](docs/decisions.md) |

The [README.md](README.md) is the top-level index and links to all of the above.
**When you change routes, RBAC, config, or architecture, update the matching doc
in `/docs` (and the README if the index changes) in the same change.**

## Architecture rules (do not violate)

- **ERPNext choke point:** only `backend/integrations/erpnext.py` may talk to
  ERPNext. Everything else goes through `ERPNextClient` / the domain wrappers.
  The frontend must never call ERPNext directly.
- **Outbound HTTP is confined to `integrations/`.** Today that is `erpnext.py`
  and `control_plane.py` — no `httpx` anywhere else in the backend.
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

A deployment may **retire** a role it does not use via `DISABLED_ROLES` — the
role can no longer be assigned, but keeps its permissions and its tests. Do not
delete a role from `Role` because one workspace has no use for it: the product
is multi-tenant, and the next workspace may want it.

## Commands

```bash
# Backend (backend/)
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
pytest                        # 416 tests; ERPNext faked, temp SQLite — no live ERPNext
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

## ERPNext will reject what the tests accept

The in-memory fake in `backend/tests/fakes.py` stores whatever it is given. It
does not enforce mandatory fields, link validation, child tables, tree rules or
fiscal-year bounds. **Every defect below shipped with a green suite and was found
only by driving a real instance.** Assume this class of bug is present until
exercised against live ERPNext.

Write tests that assert on the **payload sent to ERPNext**, not on the response.
A response can look correct while the document is silently wrong.

Traps, each of which has already cost a production bug:

- **Tree roots are never selectable.** `All Customer Groups`, `All Item Groups`,
  `All Warehouses` are containers. ERPNext refuses them on a transaction
  ("Cannot select a Group type…", "Group node warehouse is not allowed"). Never
  default a field to one — that broke customer creation, and filed 12 items
  under a category nothing can group by. Filter pickers to `is_group = 0`, and
  exclude `disabled = 1` too.
- **Mandatory child tables.** A Maintenance Visit needs a `purposes` row with
  `service_person` and `work_done`. Missing child rows fail only against real
  ERPNext.
- **`posting_date` is ignored without `set_posting_time = 1`.** Backdating
  silently posts to today, so an invoice lands in the wrong period.
- **Postings must fall inside an active Fiscal Year.** A fresh site has only the
  current year, which is why opening balances — invoices raised *before* the
  cutover — must post on the start date, not their original date.
- **`set_only_once` fields cannot be changed, ever.** The company abbreviation is
  suffixed onto every account name; the only way to change it is to rebuild the
  site. Decide it before the wizard runs.
- **List queries do not return child tables.** `GET /sales` cannot include line
  items; a detail view must fetch the document by id. Totals still look right,
  which makes this read as a display glitch rather than missing data.
- **A submitted document cannot be edited, only cancelled and amended.** The
  fake happily mutates a doc at `docstatus = 1`; ERPNext refuses everything but
  `allow_on_submit` fields. Correcting an invoice means cancel + re-post with
  `amended_from`, which **changes its number** (`…-00007` → `…-00007-1`) and is
  two calls, not one transaction. Cancel is itself refused once a payment is
  allocated. See `SalesRepository.amend`.
- **The setup wizard leaves the company unusable.** Default accounts are unset or
  matched by number prefix (the receivable control came out as an accrued-interest
  account). Run `scripts/configure_company_accounts.py` on every new site — see
  [docs/fresh-install.md](docs/fresh-install.md).

## Operating a live deployment

Once a client is entering data, treat the instance as production:

- **Back up before any ERPNext data change** (`scripts/backup-remote.sh --force`).
  Restores are proven; `scripts/restore.sh --latest --dry-run` verifies weekly.
- **Disable warehouses and master data, never delete.** ERPNext keeps stock
  ledger entries against a warehouse forever. Repoint every default *before*
  disabling — a default pointing at a disabled record fails validation later,
  far from the change that caused it.
- **Verify a deploy by comparing commit hashes**, not by asking whether the site
  responds. A failed `git pull` leaves the previous build serving happily.
- **Never copy files to the server.** Commit, push, then pull. Untracked files in
  the working tree abort `git pull`, and the deploy silently does not happen.
- Warn before deploying; a rebuild is ~30s of 502 for whoever is mid-form.

## Gotchas that cost real time

- **`bench console` mangles multi-line scripts.** It feeds stdin to IPython,
  which splits cells and dedents function bodies. Pipe one line instead:
  `echo 'exec(open("/tmp/x.py").read(), globals())' | bench --site … console`.
  The `globals()` matters — without it, names bound at module level are invisible
  to functions defined in the same file.
- **`docker compose exec -T` consumes stdin.** An informational query will eat a
  confirmation prompt's input. Add `</dev/null` to every exec that is not meant
  to read.
- **A sync FastAPI dependency runs in a threadpool**, so a ContextVar it sets is
  invisible to middleware. Pass request-scoped values through the ASGI `scope`
  (see how `get_current_user` publishes `audit_actor`).
- **`PUT /settings/branding` replaces the whole document.** Omitted fields are
  written as empty. Read, modify, send back whole.
- **`.env` is not a shell script.** Sourcing it executes it. Read specific keys
  with the `env_get` helper the scripts share.

## Expectations

- Add/adjust tests for backend changes; run `pytest` in **both** `backend/` and
  `platform/api/` (must stay green).
- Verify frontend changes with `npm run build` in **both** `frontend/` and
  `platform/ui/`.
- Don't add business logic to routers; don't fabricate ERPNext data.
- Don't hardcode "EquiMed" in user-facing frontend copy — it is white-labelled.
- Keep `/docs` accurate — it is the source of truth for this project.
- A green suite is necessary, not sufficient. Before calling ERPNext-facing work
  done, exercise it against a real instance with realistic data — prior-year
  dates, accented names, a tree-root default, a quantity larger than stock.
- Prove a test can fail. Mutate the fix, watch the test go red, restore. Several
  "fixes" here were inert until that check caught them.
