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

**Errors:** `401` missing/invalid/expired token, `403` authenticated but the
role is not permitted, `404` not found, `409` conflict (duplicate), `422`
request validation, `502` ERPNext unreachable/upstream error. Bodies are
`{ "detail": "<message>" }`.

### Roles

`Administrator`, `Manager`, `Sales`, `Store Keeper`, `Accountant`,
`Biomedical Engineer`. **Administrator is implicitly allowed on every endpoint.**
Per-endpoint access is listed below as **view** (read) and **manage** (write).

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
| GET | `/finance/reports/income-statement` | ERPNext P&L; query `company` (req), `fiscal_year`, `from_date`, `to_date`, `periodicity` |
| GET | `/finance/reports/balance-sheet` | ERPNext Balance Sheet; same query params |

---

## Dashboard  `/api/dashboard`  — *any authenticated user*

`GET /api/dashboard` → `{ revenue_today, outstanding_customers,
outstanding_suppliers, inventory_value, low_stock_count, revenue_trend[],
recent_activity[] }` (aggregated from ERPNext invoices, payments and bins).

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
