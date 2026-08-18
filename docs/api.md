# EquiMed — API Documentation

The backend is a **FastAPI** service that the Next.js frontend calls. It owns
authentication/RBAC in its own database and proxies all business data to
**ERPNext** through a single integration layer.

- **Base URL:** `/api` (the FastAPI app runs with `root_path=/api`; Caddy routes
  `/api/*` → backend, stripping the prefix).
- **Interactive docs (OpenAPI):** `http://localhost/api/docs` — the **Authorize**
  button drives the OAuth2 password flow. Raw schema at `/api/openapi.json`.
- **Format:** JSON request/response bodies; money is XAF (integer minor-unit-less).

---

## Authentication

JWT bearer tokens (HS256). Log in with the OAuth2 *password* flow — the
`username` field is the user's **email**.

```
POST /api/auth/login          # form-encoded: username=<email>&password=<pw>
  → 200 { "access_token": "<jwt>", "refresh_token": "<opaque>",
          "token_type": "bearer", "expires_in": 3600 }

POST /api/auth/refresh        # { "refresh_token": "<opaque>" } → a new pair
GET  /api/auth/me             # Authorization: Bearer <jwt>  → current user
POST /api/auth/logout         # revokes the session server-side
```

Sessions are renewed rather than expiring out from under the user — see
[Authentication](#authentication-apiauth) below for the rotation rules.

Send the token on every other request:

```
Authorization: Bearer <access_token>
```

**Errors:** `401` missing/invalid/expired token, `402` the tenant's plan does not
include the capability (or the workspace is suspended), `403` authenticated but
the role is not permitted, `404` not found (or no workspace on this hostname),
`409` conflict (duplicate), `410` workspace archived, `422` request validation,
`423` workspace still provisioning, `502` ERPNext unreachable/upstream error.
Bodies are `{ "detail": "<message>" }`.

### Roles

`Administrator`, `Manager`, `Sales`, `Store Keeper`, `Accountant`,
`Biomedical Engineer`. **Administrator is implicitly allowed on every endpoint.**
Per-endpoint access is listed below as **view** (read) and **manage** (write).

The table in this document is mirrored by hand in
`backend/tests/test_rbac_matrix.py`, which walks **every route × every role** and
asserts denied roles get exactly `403`. Two properties are enforced there:

- *completeness* — a route with no declared expectation fails the suite, so a
  new endpoint cannot ship without someone stating who may reach it;
- *enforcement* — a widened or removed guard fails the suite, which is why the
  expectations are restated by hand rather than read back from `require_roles`.

Change a guard and you change that file, and this table, in the same commit.

The frontend navigation mirrors the same matrix in `frontend/lib/role.ts`
(`NAV_ROLES`) so the menu does not advertise pages the API refuses. That is a
usability measure, never a security one — the API is the only enforcement point,
and it is enforced independently of what the UI chooses to show.

### Tenancy

Every request is resolved to a tenant from the `Host` header before auth runs.
In single-tenant deployments this is invisible — one implicit tenant, resolved
statically. On the SaaS plane:

- an unknown hostname returns `404`, a suspended workspace `402`, one still
  provisioning `423`, an archived one `410` — all *before* the token is examined;
- access tokens carry a `tid` claim which must match the resolved tenant, so a
  token minted on one workspace is inert on another;
- some routes additionally require a plan feature and return `402` if the plan
  does not include it.

See [multi-tenancy.md](multi-tenancy.md).

---

## Audit log  `/api/audit`  — *Administrator*

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/audit` | Filter by `actor_id`, `action`, `resource_type`, `succeeded`, `since`, `until`. `limit` ≤ 500. |

Every state-changing request (`POST`/`PUT`/`PATCH`/`DELETE`) is recorded by
middleware, so coverage does not depend on anyone remembering to call a logger.
Each entry carries the actor (id, email, role at the time), a stable action verb
(`customer.create`), the resource, status, outcome, client IP, user agent, a
`request_id` matching the application logs, and a server-side UTC timestamp.

**Refusals are recorded too** — a 403 is usually the entry worth reading.

**Bodies are never stored.** They would carry passwords on `/auth` routes and
customer data everywhere else, turning the audit trail into a second, less
guarded copy of the database.

**Append-only.** No route offers write, update or delete, and the repository has
no such method. Reading the log is itself audited (`audit.read`).

## Authentication  `/api/auth`

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| POST | `/auth/login` | public | Returns `access_token`, `refresh_token`, `expires_in`. |
| POST | `/auth/refresh` | public | Exchanges a refresh token for a new pair. |
| POST | `/auth/logout` | authenticated | Revokes the session server-side. |
| GET | `/auth/me` | authenticated | The current user. |

Access tokens are JWTs valid for `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60) and
cannot be withdrawn early — which is why they are short-lived and why refresh
tokens are **not** JWTs.

Refresh tokens are opaque, stored as a SHA-256 hash, and **single-use**: every
refresh rotates. Presenting an already-rotated token means two parties hold the
same credential, so the entire rotation family is revoked — the safe reading of
a replay is theft, and there is no way to tell which holder is the attacker.

`REFRESH_TOKEN_EXPIRE_DAYS` (default 30) bounds a session; deactivating a user
invalidates theirs immediately.

> Clients must single-flight the refresh. When a token expires, every in-flight
> request fails at once; independent refreshes would race, and since the tokens
> are single-use the losers would look like reuse and revoke the session. The
> web client does this in `lib/session.ts`.

## Public  `/api/public`  — *unauthenticated, tenant-scoped*

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/public/branding` | branding needed to paint the sign-in screen |

Deliberately outside auth: a user must see whose login page they are on before
they have a token. Still behind tenant resolution, so an unknown host `404`s.
Returns only `{ tenant, app_name, short_name, tagline, logo_*, favicon_*,
light_tokens, dark_tokens, font_*, default_theme }` — no support addresses, no
dashboard layout.

---

## Internal  `/api/internal`  — *control plane → tenant app*

Shared-secret authenticated (`X-Internal-Token`), exempt from tenant resolution
because these act *on* a named tenant rather than being served *as* one. **Never
route this prefix through the public proxy.** Unset token = every call refused.

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/internal/tenants/{id}/bootstrap` | create the workspace's first admin, profile and branding (idempotent) |
| DELETE | `/internal/tenants/{id}` | erase the workspace's app-DB rows (offboarding) |

---

## Users  `/api/users`  — *Administrator only*

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/users` | list (Administrator) |
| POST | `/users` | create (Administrator) |
| GET | `/users/{id}` | Administrator, **or** the user reading themselves |
| PUT | `/users/{id}` | update role / status / password (Administrator) |
| DELETE | `/users/{id}` | delete (Administrator) |

`User` = `{ id, email, full_name, role, is_active, created_at, updated_at }`.
Passwords are bcrypt-hashed and never returned.

---

## Customers  `/api/customers`  → ERPNext `Customer`

- **view:** Manager, Sales, Accountant · **manage:** Manager, Sales

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/customers` | query: `search` (name), `customer_type`, `group`, `limit`, `start` |
| POST | `/customers` | create |
| GET | `/customers/{id}` | `{id}` = ERPNext document name |
| PUT | `/customers/{id}` | update |
| DELETE | `/customers/{id}` | delete |

`Customer` = `{ id, name, customer_group, customer_type, territory,
contact_person, phone, email, address, tax_id, outstanding_balance, disabled }`.

---

## Suppliers  `/api/suppliers`  → ERPNext `Supplier`

- **view:** Manager, Accountant, Store Keeper · **manage:** Manager

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/suppliers` | query: `search`, `supplier_type`, `group`, `limit`, `start` |
| POST/GET/PUT/DELETE | `/suppliers[/{id}]` | CRUD |

`Supplier` adds `lead_time_days` to the customer-shaped fields.

---

## Products  `/api/products`  → ERPNext `Item`

- **view:** any authenticated user · **manage:** Manager

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/products` | query: `search` (name), `category`, `limit`, `start` |
| POST/GET/PUT/DELETE | `/products[/{id}]` | `{id}` = SKU / `item_code` |

`Product` = `{ id, name, sku, barcode, category, manufacturer,
purchase_price, selling_price, unit, image, disabled }`.

---

## Inventory  `/api/inventory`

- **view:** Manager, Store Keeper, Accountant, Sales · **manage:** Manager, Store Keeper

| Method | Path | Notes |
| --- | --- | --- |
| GET/POST | `/inventory/warehouses` | list / create (ERPNext `Warehouse`) |
| GET/PUT/DELETE | `/inventory/warehouses/{id}` | read / update / delete |
| GET/POST | `/inventory/batches` | list / create (ERPNext `Batch`, with expiry) |
| GET | `/inventory/batches/{id}` | read |
| GET | `/inventory/stock` | stock levels (ERPNext `Bin`); query `item_code`, `warehouse` |
| POST | `/inventory/receive` | Goods Received → submitted `Stock Entry` (Material Receipt) |
| POST | `/inventory/issue` | Goods Issued → submitted `Stock Entry` (Material Issue) |

Movement body: `{ warehouse, items: [{ item_code, qty, batch_no?, rate? }] }`.

---

## Sales  `/api/sales`  → ERPNext `Sales Invoice`

- **view:** Manager, Sales, Accountant · **create:** Manager, Sales ·
  **amend (edit a posted invoice):** Manager

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/sales` | query: `search` (customer), `status`, `limit`, `start`. Cancelled invoices are excluded |
| POST | `/sales` | create **+ submit** to the ledger |
| GET | `/sales/{id}` | invoice with line items |
| PUT | `/sales/{id}` | **cancel + amend** — see below. Returns the *replacement*, under a new id |

Create body: `{ customer, items: [{ item_code, qty, rate }], due_date?,
posting_date?, remarks?, update_stock?, taxes_and_charges? }`.

`SalesInvoice` also returns `update_stock`, `taxes_and_charges`, `amended_from`,
`is_cancelled` and `is_opening`.

### Editing a posted invoice

ERPNext has no in-place update for a submitted document, so `PUT /sales/{id}`
**cancels** the invoice and posts a corrected copy in its place:

- **The invoice number changes.** `ACC-SINV-2026-00007` is replaced by
  `ACC-SINV-2026-00007-1`. Read the id back from the response; the id in the
  path now names a cancelled document.
- **The body replaces the whole document.** An omitted field is written empty,
  not preserved — leave out `taxes_and_charges` and the VAT comes off the
  invoice; leave out `update_stock` and the cancel returns the goods to stock
  without the replacement taking them out again.
- **The original is kept, reversed.** It carries `is_cancelled`, and the
  replacement points back at it through `amended_from`. Listing excludes
  cancelled invoices so one sale is not shown twice.
- **Refused with 409** when the invoice is an opening balance from the
  first-time books setup, or when a payment has already been received against
  it (cancel the payment, or raise a credit note). Both are checked *before*
  anything is cancelled.
- **Resumable.** The cancel and the re-post are two calls, not one transaction.
  If the second fails, calling `PUT` again finishes the job; it returns the
  existing replacement rather than posting a second one.

---

## Purchases  `/api/purchases`  → ERPNext `Purchase Invoice`

- **view:** Manager, Accountant, Store Keeper · **create:** Manager ·
  **amend (edit a posted bill):** Manager

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/purchases` | query: `search` (supplier), `status`, `limit`, `start`. Cancelled bills are excluded |
| POST | `/purchases` | create + submit; body `{ supplier, items, bill_no?, posting_date? }` |
| GET | `/purchases/{id}` | bill with line items |
| PUT | `/purchases/{id}` | cancel + amend, identical semantics to `PUT /sales/{id}` above |

---

## Equipment  `/api/equipment`  → ERPNext `Serial No`

- **view:** Manager, Biomedical Engineer, Sales, Store Keeper · **manage:** Manager, Biomedical Engineer

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/equipment` | query: `search` (serial), `status`, `customer`, `limit`, `start` |
| POST/GET/PUT/DELETE | `/equipment[/{id}]` | CRUD; `{id}` = serial number |
| POST | `/equipment/{id}/install` | mark Installed, stamp installation date; body `{ customer?, installation_date? }` |

`Equipment` = `{ id, serial_no, item_code, item_name, customer,
installation_date, warranty_expiry_date, status }`.

---

## Maintenance  `/api/maintenance`  → ERPNext `Maintenance Visit`

- **view:** Manager, Biomedical Engineer, Sales · **manage:** Manager, Biomedical Engineer

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/maintenance` | query: `search` (customer), `status`, `engineer`, `limit`, `start` |
| POST/GET/PUT/DELETE | `/maintenance[/{id}]` | CRUD; `{id}` = ticket number |
| POST | `/maintenance/{id}/complete` | set Completed, capture signature; body `{ parts_used?, signed? }` |

---

## Finance  `/api/finance`  — *Manager, Accountant*

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/finance/summary` | receivables, payables, net position, overdue, outstanding lists (from invoices) |
| GET | `/finance/receivable` | aged customer ledger (open Sales Invoices, Current/1-30/31-60/61-90/90+ buckets) |
| GET | `/finance/payable` | aged supplier ledger (open Purchase Invoices, same buckets) |
| GET | `/finance/cash-book` | cash-account GL movements with running balance; query `company`, `from_date`, `to_date` |
| GET | `/finance/bank-book` | bank-account GL movements with running balance; same query params |
| GET | `/finance/trial-balance` | closing debit/credit per leaf account (ERPNext Trial Balance); query `company` (req), `fiscal_year`, `from_date`, `to_date` |
| GET | `/finance/cash-flow` | direct-method cash movement (opening, inflows/outflows by voucher type, closing) from cash & bank ledgers; query `company`, `fiscal_year`, `from_date`, `to_date` |
| GET | `/finance/reports/income-statement` | ERPNext P&L; query `company` (req), `fiscal_year`, `from_date`, `to_date`, `periodicity` |
| GET | `/finance/reports/balance-sheet` | ERPNext Balance Sheet; same query params |

---

## Dashboard  `/api/dashboard`  — *any authenticated user, filtered by role*

`GET /api/dashboard` → aggregated from ERPNext invoices, payments and bins.

Every signed-in user may call it, but **the fields returned depend on their
role**. Withheld fields are *absent from the JSON*, not null and not zero —
zero is a real figure ("no revenue today") and has to stay distinguishable from
"not permitted".

| Tier | Fields | Roles |
| --- | --- | --- |
| Operational | `low_stock_count`, `low_stock_items[]`, `expiring_batches[]` | everyone |
| Commercial | `revenue_today`, `revenue_trend[]`, `revenue_by_segment[]`, `top_customer`, `recent_activity[]` | Manager, Accountant, Sales |
| Financial | `outstanding_customers`, `outstanding_suppliers`, `inventory_value` | Manager, Accountant |

Administrator sees everything. An unrecognised role gets the operational tier
only — the policy fails closed.

Why this exists: `/finance/*` is Manager + Accountant, and the dashboard carries
the same figures. Left role-agnostic it is a side door — a Store Keeper denied
the finance pages would read revenue and receivables off their landing page
instead. The filter is applied server-side in
`services/dashboard_service.py` (`VISIBLE_FIELDS`); hiding a card in the
frontend is presentation, not protection.

Pinned by `backend/tests/test_dashboard_rbac.py`, which asserts on the HTTP
payload rather than the projection helper — a filter lost between service and
router would still pass a unit test of the helper.

## Reports  `/api/reports`  — *Manager, Accountant*

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/reports/{report_key}/pdf` | Branded, **cryptographically signed (PAdES)** PDF. `report_key` ∈ `receivables`, `payables`, `current-stock`, `low-stock`, `income-statement`, `balance-sheet`, `trial-balance`, `cash-flow`, `dashboard`. Query (per report): `company` (req. for statements/trial-balance/cash-flow), `fiscal_year`, `from_date`, `to_date`, `warehouse`. Returns `application/pdf` (attachment). |

Rendering: reportlab letterhead (logo, legal details, signatory block) → signed with
pyHanko using a self-signed certificate auto-provisioned in `/app/data/signing`
(persistent `backend-data` volume). Data is pulled from the finance/inventory
services; branding comes from the company profile below.

## Settings  `/api/settings`

Two distinct resources: the tenant's **legal identity** (printed on PDFs) and
its **application skin** (the running UI). Both are per-tenant, stored in the
app DB, never in ERPNext.

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| GET | `/settings/company-profile` | any authenticated | Legal identity: letterhead, signatory, RC/NIU, accent + logo data-URI. |
| PUT | `/settings/company-profile` | Manager, Accountant | Full replacement of the editable fields. |
| GET | `/settings/branding` | any authenticated | Application skin: product name, logos, theme tokens, dashboard layout. |
| PUT | `/settings/branding` | Manager, Accountant · plan `branding` | Full replacement. Rejects anything not in the token allowlist. |


> **`PUT /settings/branding` replaces the whole document.** `BrandingUpdate` has
> the same shape as the read model, so any field absent from the body is written
> as its default — an empty string — not left alone. Sending only
> `{"light_tokens": …}` clears the app name, short name and tagline, which then
> fall back to the `BRAND_*` environment defaults. Read the current branding,
> modify it, and send it back whole. The web client already does this; the trap
> is for anyone calling the API directly.
| PUT | `/settings/branding/dashboard` | Manager, Accountant · plan `dashboard_layout` | Replace the dashboard widget composition. |
| POST | `/settings/branding/dashboard/reset` | Manager, Accountant | Restore the default dashboard layout. |

**Branding validation** is a security control, not input hygiene — these values
are rendered into a `<style>` block. Requests are **rejected**, never sanitised:
theme token *names* must be in the allowlist mirroring `globals.css`; *values*
must be a bare hex colour; fonts must match a conservative family-name pattern
(no `url()`, quotes or semicolons); images must be `data:image/...` URIs under
512 KB. Anything else is `422`.

**Dashboard layout** is `{"widgets": [{id, visible, span, viz, title}]}`. Widget
ids and permitted `viz` values are fixed server-side — a KPI tile cannot be
configured as a chart, and duplicates or a `span` outside 1–4 are `422`.

| Widget | `viz` options |
| --- | --- |
| `chart.revenue_trend` | `line`, `area`, `bar` |
| `chart.segment_mix` | `donut`, `progress`, `stacked-bar` |
| `kpi.*`, `list.*`, `table.*`, `feed.*` | none |

## Health  — *public*

`GET /api/health` (liveness) · `GET /api/health/erpnext` (ERPNext reachability).

---

## ERPNext custom fields

Non-native attributes are stored on ERPNext Custom Fields (`custom_*`) that must
exist on the target DocTypes — e.g. `custom_contact_person`, `custom_phone`,
`custom_email`, `custom_address` (Customer/Supplier); `custom_barcode`,
`custom_manufacturer`, `custom_purchase_price`, `custom_selling_price` (Item);
`custom_installation_date`, `custom_status` (Serial No); `custom_engineer`,
`custom_parts_used`, `custom_customer_signed`, `custom_status` (Maintenance Visit).

---

## Control-plane API  `/papi`  — *SaaS plane only*

A **separate service** (`platform/api`) with its own database, its own signing
key and its own operator accounts — not a role inside the tenant app. A tenant
Administrator is powerful inside one workspace; a platform operator can suspend
every workspace. Operator tokens carry `aud: equimed-control-plane`, so the two
token families are not interchangeable in either direction.

### Operator RBAC

| Role | Read | Create/edit/provision | Suspend/resume/archive | Plans | Purge | Operators |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| Owner | ● | ● | ● | ● | ● | ● |
| Operator | ● | ● | ● | | | |
| Support | ● | | | | | |
| Billing | ● | | | ● | | |

Unlike the tenant app, Owner is **not** implicitly allowed everywhere — it is
declared on each route.

### Endpoints

| Method | Path | Access | Notes |
| --- | --- | --- | --- |
| POST | `/auth/login` | public | OAuth2 password flow; `username` is the operator email. |
| GET | `/auth/me` | any operator | Current operator. |
| GET/POST | `/operators` | Owner | List / create platform operators. |
| PATCH/DELETE | `/operators/{id}` | Owner | Refuses to disable the last active Owner. |
| GET | `/tenants` | any operator | Filter by `status`, `plan_code`, `search`. |
| GET | `/tenants/stats` | any operator | Counts by status. |
| GET | `/tenants/{id}` | any operator | Never returns the ERPNext secret — only `has_erpnext_secret`. |
| POST | `/tenants` | Owner, Operator | Register a workspace (`pending`; serves no traffic yet). |
| PATCH | `/tenants/{id}` | Owner, Operator | Edit details / change plan. |
| POST | `/tenants/{id}/provision` | Owner, Operator | Create the ERPNext site + first admin. Idempotent. |
| POST | `/tenants/{id}/suspend` | Owner, Operator | The kill switch; takes effect within the resolver cache TTL. |
| POST | `/tenants/{id}/resume` | Owner, Operator | `409` if the workspace was never provisioned. |
| POST | `/tenants/{id}/archive` | Owner, Operator | Take offline permanently, keeping data. |
| DELETE | `/tenants/{id}?confirm=<id>` | **Owner** | Irreversible. Requires `archived` + matching confirmation. |
| POST | `/tenants/{id}/domains` | Owner, Operator | `402` unless the plan includes `custom_domain`. |
| POST | `/tenants/{id}/domains/{host}/verify` | Owner, Operator | Unlocks TLS issuance for that host. |
| DELETE | `/tenants/{id}/domains/{host}` | Owner, Operator | `409` on the last remaining domain. |
| GET | `/plans` · `/plans/features` · `/plans/{code}` | any operator | Catalogue + capability vocabulary. |
| POST | `/plans` · PATCH `/plans/{code}` | Owner, Billing | `409` when deactivating a plan that has workspaces. |
| GET | `/audit` | any operator | Append-only log; filter by `tenant_id` / `action`. |

### Internal (machine-to-machine)

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| GET | `/internal/tenants/resolve?host=` | `X-Internal-Token` | The tenant app's hot path. The **only** endpoint that decrypts a tenant's ERPNext secret. |
| GET | `/internal/tls/check?domain=` | none | Caddy's on-demand-TLS ask endpoint. `200` = issue, `403` = refuse. Unauthenticated by necessity (Caddy cannot send headers); answers a single yes/no about a hostname already observable in DNS. |

Full design and threat model: [multi-tenancy.md](multi-tenancy.md).
