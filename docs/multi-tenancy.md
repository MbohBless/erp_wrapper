# Multi-tenancy, white-labelling and the control plane

How EquiMed serves one customer on their own hardware **and** many customers on
a shared plane, from one codebase.

- [The two products](#the-two-products)
- [How a tenant is resolved](#how-a-tenant-is-resolved)
- [Isolation: what actually stops a leak](#isolation-what-actually-stops-a-leak)
- [The control plane](#the-control-plane)
- [Provisioning and the tenant lifecycle](#provisioning-and-the-tenant-lifecycle)
- [Domains and TLS](#domains-and-tls)
- [White-labelling](#white-labelling)
- [Configurable dashboards](#configurable-dashboards)
- [Plans and feature gating](#plans-and-feature-gating)
- [Running it](#running-it)
- [Risks and what to watch](#risks-and-what-to-watch)

---

## The two products

Tenancy is a **deployment mode**, not a fork. `TENANCY_MODE` decides which
product a given stack is:

| | `single` (self-hosted / dedicated) | `multi` (shared SaaS) |
| --- | --- | --- |
| Tenants per stack | one, implicit | many |
| Tenant resolution | static, from `config.Settings` | per request, from the `Host` header |
| Control plane | **not used at all** | required |
| ERPNext | one site, coordinates in `.env` | one site per tenant, coordinates in the registry |
| First admin | seeded from `FIRST_ADMIN_*` | created by the control plane at provisioning |
| Features | all | whatever the plan includes |

A customer running EquiMed on their own hardware has **no runtime dependency on
our platform**. That is deliberate: a self-hosted product that phones home is a
harder sale and a worse product.

---

## How a tenant is resolved

Every request passes through `TenantMiddleware` (`backend/tenancy/middleware.py`)
before anything else — before CORS, before auth, before the database.

```
Request ──▶ TenantMiddleware
              │
              ├─ Host / X-Forwarded-Host  ──▶ TenantResolver
              │                                 ├─ StaticTenantResolver   (single)
              │                                 └─ ControlPlaneResolver   (multi, TTL-cached)
              │
              ├─ unknown host      ──▶ 404
              ├─ suspended         ──▶ 402   (billing; paying resolves it)
              ├─ provisioning      ──▶ 423   (exists, not servable yet)
              ├─ archived          ──▶ 410
              │
              └─ active ──▶ bind TenantContext ──▶ app
```

The resolved `TenantContext` is bound to a `ContextVar` and read through exactly
one accessor, `current_tenant()`. That single choke point is what makes tenant
isolation auditable: there is one place to review, not one per router.

It carries the ERPNext coordinates as **data**, which is what lets the same
process serve one tenant or many:

```python
TenantContext(
    id="acme", name="Acme Medical", status="active", plan="enterprise",
    erpnext_url="http://erpnext-nginx:8080",
    erpnext_site="acme.erp.local",        # Frappe resolves the site from Host
    erpnext_api_key=..., erpnext_api_secret=...,
    features=frozenset({"branding", "dashboard_layout"}),
)
```

`erpnext_site` is the multi-site lever. A Frappe bench serving many sites picks
the site from the HTTP `Host` header, so several tenants share one `erpnext_url`
while each reads and writes its own database. For a dedicated instance, leave it
blank — `erpnext_url` already identifies the tenant.

### Why the tenancy model is ERPNext-site-per-tenant

Three options were considered:

1. **Stack per tenant** — zero code change, but ~8 containers and 4–6 GB per
   customer. Kept as the paid *dedicated instance* tier.
2. **Frappe multi-site on a shared bench** — one bench, one database per site.
   **This is what the SaaS plane uses.** Isolation is a database boundary, which
   is the strongest guarantee available without paying for option 1.
3. **One site, one ERPNext *Company* per tenant** — rejected. ERPNext scopes
   *transactions* by Company but master data (Items, Customers, Suppliers) is
   global to a site. Customer A would see Customer B's customer list. Company-
   per-tenant is fine for one business with several legal entities; it is not a
   tenancy boundary.

### Caching, and why the TTL is short

`ControlPlaneTenantResolver` caches resolutions for `TENANT_CACHE_TTL` seconds
(default 30). That TTL is also **the upper bound on how long a suspension takes
to take effect** — which is the real constraint on how large it can be.

Two deliberate behaviours:

- Unknown hosts are cached for only 5 seconds. A host that 404s today is usually
  a tenant about to be provisioned.
- If the control plane is unreachable, an **already-resolved** host keeps being
  served from its stale entry, while an unknown host fails closed with 503. A
  control-plane blip must not take every customer offline, but it must also not
  become a way to reach an unknown workspace.

---

## Isolation: what actually stops a leak

One shared backend process serves every tenant, so isolation is enforced in the
application. Four independent mechanisms, in order of the request:

**1. The middleware.** Unknown and suspended tenants never reach a router.

**2. The `tid` JWT claim.** All workspaces share one signing key, so a token
minted for tenant A is *cryptographically valid* on tenant B's host. The claim
check in `get_current_user` is what actually stops the replay:

```python
if payload.get("tid") != tenant.id:
    raise credentials_exc
```

**3. Tenant-scoped repositories.** Every app-DB repository is constructed for
one tenant and filters on it. There is intentionally no "get any user by id"
method — isolation is enforced in the data layer, not left to each caller. Writes
*stamp* `tenant_id` rather than trusting the payload:

```python
def add(self, user: User) -> User:
    user.tenant_id = self.tenant_id   # stamped, never trusted
```

**4. ERPNext site separation.** Business data never shares a database at all.

### Email uniqueness

`users.email` is unique **per tenant**, not globally
(`UniqueConstraint("tenant_id", "email")`). Two customers must each be able to
have an `admin@` account. The migration in `main.py::_ensure_user_indexes` drops
the old global unique index when upgrading an existing install.

### The tests are the security posture

`backend/tests/test_tenancy.py` is the load-bearing test file. Every tenant in it
shares **one SQLite database on purpose** — that is the hostile case. If
isolation holds on a shared database it holds on separate ones. Treat a failure
there as an incident, not a bug. It asserts, among other things:

- a token from tenant A is rejected on tenant B (401),
- a password valid on one workspace does not authenticate on another,
- `/users` never returns another tenant's rows,
- the ERPNext client is built from the *request's* tenant credentials,
- purging one workspace leaves the others untouched.

---

## The control plane

A **separate service** (`platform/api`) with its own database, its own signing
key, and its own operator accounts. It is not a role inside the tenant app, and
that is not an accident: a tenant administrator is powerful inside one
workspace; a platform operator can suspend every workspace at once. The two must
never be the same record or authenticated by the same token.

```
platform/api        FastAPI — registry, plans, operators, audit, provisioning
platform/ui         Next.js operator console (its own palette, its own /papi prefix)
```

### Operator roles

| Role | Read | Create / edit / provision | Suspend / resume / archive | Plans | Purge | Manage operators |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| Owner | ● | ● | ● | ● | ● | ● |
| Operator | ● | ● | ● | | | |
| Support | ● | | | | | |
| Billing | ● | | | ● | | |

Unlike the tenant app, Owner is **not** implicitly allowed everywhere — it is
listed on each route, so this matrix can be read straight off the routers.

### Secrets at rest

Tenant ERPNext API secrets are encrypted in the registry (`utils/crypto.py`,
Fernet). A leaked control-plane database would otherwise be a leak of every
customer's ERP. The admin API reports `has_erpnext_secret: true` but **never
returns the value** — the only endpoint that decrypts it is
`/internal/tenants/resolve`, on the internal network behind a shared secret.

Set `SECRET_ENCRYPTION_KEY` explicitly in production. Left unset, the key is
derived from `PLATFORM_JWT_SECRET_KEY`, and rotating that would make every
stored credential unreadable.

### The audit log

Every mutating endpoint writes one row (`audit_log`) with the operator who
caused it. The repository has no update or delete method — if the log can be
edited from the application it is not evidence of anything.

---

## Provisioning and the tenant lifecycle

```
pending ──provision──▶ provisioning ──▶ active
active  ──suspend────▶ suspended ──resume──▶ active
any     ──archive────▶ archived  ──purge───▶ (deleted)
```

Two rules hold throughout:

- **Status only advances after the underlying work succeeded.** A failed
  `bench new-site` leaves the tenant `pending`; a failed bootstrap leaves it
  `provisioning` — locked and visibly incomplete — never `active`.
- **Every transition is audited** with its operator.

Provisioning is two steps against two different systems:

1. `Provisioner.create_site()` — creates the ERPNext site.
2. `TenantAppClient.bootstrap()` — calls the tenant app's
   `POST /internal/tenants/{id}/bootstrap` to create the workspace's first
   administrator, company profile and branding row.

Step 2 is a **callback, not a database write**: the control plane owns *who* a
tenant is, the tenant app owns that tenant's users. Neither writes to the
other's schema. Both steps are idempotent, because the usual reason to re-run
provisioning is that the first attempt died halfway.

### Provisioner backends

| `PROVISIONER` | Behaviour |
| --- | --- |
| `noop` (default) | Records intent, changes nothing. An operator can drive the whole lifecycle before any infrastructure exists. |
| `bench` | Shells out to a Frappe bench over `docker exec`. |

> **`bench` mounts the Docker socket into `platform-api`.** Anything that can
> reach that container can transitively run commands on the host's Docker
> daemon. Run the control plane on its own network, never expose `/internal`
> publicly, and prefer a dedicated provisioning worker once the platform grows
> past a handful of tenants.

### Purging

`DELETE /tenants/{id}` has two speed bumps in front of it, because it is the
only operation that destroys a customer's business records: the workspace must
already be `archived`, and the caller must repeat its id as `?confirm=`. It is
Owner-only. `drop_site` takes a backup first — an offboarding customer may still
ask for their data afterwards.

---

## Domains and TLS

Every tenant gets `<slug>.<BASE_DOMAIN>`, verified at creation. Tenants on a plan
with `custom_domain` may add their own, which they CNAME to us.

Certificates are issued **on demand** rather than from a wildcard, so no DNS
provider plugin is needed and a customer's domain works the moment they point it
at us. Caddy asks the control plane before every issuance:

```
on_demand_tls {
    ask http://platform-api:8000/internal/tls/check
    interval 2m
    burst 5
}
```

`/internal/tls/check` returns 200 only for a domain that is **registered to a
tenant, verified, and not archived**. Without that gate, anyone pointing DNS at
our IP could make us request certificates on their behalf. It is the one
internal endpoint served without the shared secret — Caddy cannot attach custom
headers — which is safe because it answers a single yes/no about a hostname
whose existence is already observable in DNS, and reveals nothing about the
tenant behind it.

Reserved slugs (`api`, `www`, `admin`, `console`, …) are refused so a tenant
cannot claim a subdomain that shadows platform infrastructure.

---

## White-labelling

Two separate resources, because they are genuinely different concerns with
different editors and different assets:

| | `CompanyProfile` | `TenantBranding` |
| --- | --- | --- |
| Owns | the tenant's **legal identity** | the tenant's **application skin** |
| Fields | legal name, address, RC/NIU, signatory | product name, logos, theme tokens, dashboard layout |
| Drives | PDF letterheads | the running UI |
| Endpoint | `/settings/company-profile` | `/settings/branding` |

The design system in `frontend/app/globals.css` is entirely CSS custom
properties, so re-skinning is a matter of overriding a handful of them at
runtime. `BrandingProvider` fetches `/public/branding` — **unauthenticated**, so
the sign-in screen is already branded — and injects the overrides as a `<style>`
block.

### Theming is a security boundary

Tenant-supplied values end up inside a `<style>` tag. `schemas/branding.py`
therefore **rejects rather than sanitises**:

- token **names** must be in `THEME_TOKENS` (the tokens `globals.css` defines),
- token **values** must be a bare hex colour,
- **fonts** must match a conservative family-name pattern — no `url()`, no
  quotes, no semicolons, so a value cannot escape its declaration,
- **assets** must be `data:image/...` URIs, so branding can never point the
  browser at a third-party host,
- assets are capped at 512 KB encoded.

`backend/tests/test_branding.py` covers the injection payloads directly
(`#fff; } body { background: url(...)`, `expression(...)`, comment escapes,
remote URLs). A silently-mangled brand colour is a support ticket; a silently-
accepted payload is a vulnerability.

The frontend re-validates the same rules in `lib/branding.tsx` before writing
CSS. The API is the boundary; the second gate costs nothing.

---

## Configurable dashboards

The dashboard is composed from data, not hard-coded. `TenantBranding.dashboard`
holds a validated widget list:

```json
{"widgets": [
  {"id": "kpi.revenue", "visible": true, "span": 1, "viz": null, "title": null},
  {"id": "chart.revenue_trend", "visible": true, "span": 3, "viz": "bar", "title": "Sales"}
]}
```

`WidgetGrid` maps over it and asks a registry for each panel. Widget ids and
allowed visualisations live in `schemas/branding.py`; the server rejects unknown
ids and mismatched viz types (a KPI tile cannot be configured as a donut chart
of one number). Tenants edit this in **Settings → Appearance**.

Charts are hand-written SVG — no charting library — which is why per-tenant viz
selection is cheap:

| Widget | Visualisations |
| --- | --- |
| `chart.revenue_trend` | `line`, `area`, `bar` |
| `chart.segment_mix` | `donut`, `progress`, `stacked-bar` |

Because the accent colour is itself white-label configurable, a fixed
categorical palette is not available. The segment mix is an ordered
composition, so it uses a **single-hue sequential ramp** stepped from the
tenant's accent, and every segment carries its name and percentage as a direct
label — identity never rests on colour alone.

Adding a widget is: a new id in `schemas/branding.py`, a case in `WidgetGrid`,
a label in `lib/dashboard.ts`.

---

## Plans and feature gating

A plan's `features` list is the contract between billing and the product. The
tenant app receives it through tenant resolution and gates routes on it:

```python
has_branding = require_feature("branding")

@router.put("/branding", dependencies=[Depends(can_edit), Depends(has_branding)])
```

A gate returns **402 Payment Required** with the plan name, not a generic 403 —
the caller can tell "you cannot" from "your plan cannot".

| Feature | Unlocks |
| --- | --- |
| `reports` | Signed PDF reporting suite |
| `budget` | Budgets and budget-vs-actual |
| `branding` | White-label theme, logos, product name |
| `dashboard_layout` | Configurable dashboard composition |
| `custom_domain` | Bring-your-own domain |
| `dedicated_erp` | Isolated ERPNext stack |

Selling a capability is a data change in the control plane, not a deploy.
Self-hosted tenants get everything — `StaticTenantResolver` grants the full set.

A plan that workspaces are currently on cannot be deactivated; it would silently
strip their features at the next resolve.

---

## Running it

### Self-hosted (default, unchanged)

```bash
cp .env.example .env
docker compose up -d --build
```

Nothing about this path changed. The app serves one implicit tenant, never
contacts a control plane, and an existing database is migrated in place —
pre-multi-tenant rows land in the `default` tenant.

### SaaS plane

```bash
cp .env.example .env
# Required, and they must not be the same value:
#   INTERNAL_API_TOKEN       shared by control plane <-> tenant app
#   PLATFORM_JWT_SECRET_KEY  operator sessions (never reuse JWT_SECRET_KEY)
#   SECRET_ENCRYPTION_KEY    encrypts tenant ERPNext credentials at rest
# Generate each with: openssl rand -hex 32

# In .env:
#   TENANCY_MODE=multi
#   CADDYFILE=Caddyfile.saas
#   BASE_DOMAIN=equimed.app
#   PLATFORM_DOMAIN=console.equimed.app

docker compose --profile saas up -d --build
```

Point `*.equimed.app` and `console.equimed.app` at the host. Sign in to the
console as `FIRST_OWNER_EMAIL`, create a workspace, then provision it.

### Tests

```bash
cd backend       && pytest    # 416 tests, incl. tests/test_tenancy.py
cd platform/api  && pytest    #  34 tests
cd frontend      && npm run build
cd platform/ui   && npm run build
```

---

## Risks and what to watch

**Per-tenant ERPNext weight is the unit economics.** ERPNext is heavy. Benchmark
a real site under load before pricing anything — this number, not the
application code, decides whether the shared plane is viable at a Cameroon SME
price point.

**Upgrades across N sites are the recurring operational tax.** `bench migrate`
has to run against every site, with a rollback plan. Budget for it as a standing
cost, not a one-off. This is the single biggest ongoing burden of the SaaS
model versus the self-hosted one.

**One shared backend means one bug is a cross-tenant leak.** The mitigations are
structural — tenant resolution in exactly one place, enforcement at the
repository layer rather than the router — and `tests/test_tenancy.py` is what
keeps them honest. Any new app-owned table must use `TenantScoped` and a scoped
repository.

**`PROVISIONER=bench` mounts the Docker socket.** See the warning above. It is
off by default for this reason.

**Backups are per-site now.** `scripts/backup.sh` enumerates every site on the
bench rather than reading a list, so a new customer cannot be silently left out
of the rotation. Copy backups off the host — a backup on the same disk is not a
backup. Offboarding still needs a tested *restore-into-a-new-site* path, which
self-hosted customers will contractually want as an export.

**No Alembic yet.** Schema changes are additive DDL in `main.py::_ensure_columns`.
That is adequate for what has shipped and will not stay adequate — introduce
Alembic before the next non-additive change.

**Two databases can disagree.** A tenant exists in the control-plane registry
*and* has rows in the tenant app's database. Purge removes both, but a failed
`bootstrap` leaves a registry row with no app rows (recoverable: re-run
provisioning). There is no periodic reconciliation job; add one if the tenant
count grows.
