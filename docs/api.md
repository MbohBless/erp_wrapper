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
  → 200 { "access_token": "<jwt>", "token_type": "bearer" }

GET  /api/auth/me             # Authorization: Bearer <jwt>  → current user
POST /api/auth/logout         # authenticated; stateless (client discards token)
```

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

- **view:** Manager, Sales, Accountant · **manage (create):** Manager, Sales

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/sales` | query: `search` (customer), `status`, `limit`, `start` |
| POST | `/sales` | create **+ submit** to the ledger |
| GET | `/sales/{id}` | invoice with line items |

Create body: `{ customer, items: [{ item_code, qty, rate }], due_date? }`.

---

## Purchases  `/api/purchases`  → ERPNext `Purchase Invoice`

- **view:** Manager, Accountant, Store Keeper · **manage (create):** Manager

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/purchases` | query: `search` (supplier), `status`, `limit`, `start` |
| POST | `/purchases` | create + submit; body `{ supplier, items, bill_no?, posting_date? }` |
| GET | `/purchases/{id}` | bill with line items |

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

## Dashboard  `/api/dashboard`  — *any authenticated user*

`GET /api/dashboard` → `{ revenue_today, outstanding_customers,
outstanding_suppliers, inventory_value, low_stock_count, revenue_trend[],
recent_activity[] }` (aggregated from ERPNext invoices, payments and bins).

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
