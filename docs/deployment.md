# EquiMed — Deployment

Everything runs via **Docker Compose** on a single VPS. Caddy is the only public
entry point.

The same stack ships in two modes, selected by `TENANCY_MODE` in `.env`:

| | `single` (default) | `multi` |
| --- | --- | --- |
| Product | self-hosted / dedicated instance | shared SaaS plane |
| Compose | `docker compose up -d --build` | `docker compose --profile saas up -d --build` |
| Caddy | `CADDYFILE=Caddyfile` | `CADDYFILE=Caddyfile.saas` |
| Extra services | — | `platform-api`, `platform-ui` |

Nothing about the single-tenant path changed; see
[multi-tenancy.md](multi-tenancy.md) for the SaaS plane.

## Prerequisites

- Docker Engine + Docker Compose v2
- ~4 GB RAM free (ERPNext + MariaDB + Redis are the heavy parts)
- A domain (optional, for automatic HTTPS)

## Quick start

```bash
cp .env.example .env          # then edit secrets (see below)
docker compose up -d --build
docker compose logs -f erpnext-create-site   # watch first-time site creation
```

First boot pulls the ERPNext image and creates the site — allow several minutes.

### Access

- App (frontend): `http://localhost/`
- API health: `http://localhost/api/health` · docs: `http://localhost/api/docs`
- ERPNext admin: `http://localhost:8080/` (login `Administrator` / `ADMIN_PASSWORD`),
  or `http://erp.localhost/` after adding `127.0.0.1 erp.localhost` to `/etc/hosts`.

## Services (`docker-compose.yml`)

| Service | Role |
| --- | --- |
| `caddy` | public reverse proxy (`:80`/`:443`): `/`→frontend, `/api/*`→backend, `erp.localhost`→ERPNext |
| `frontend` | Next.js (standalone build) |
| `backend` | FastAPI (Uvicorn) |
| `db` | MariaDB 10.6 (ERPNext) |
| `redis-cache`, `redis-queue` | Redis instances required by ERPNext |
| `erpnext-configurator` | one-shot: writes `common_site_config.json` |
| `erpnext-create-site` | one-shot: creates the site, installs `erpnext` (idempotent) |
| `erpnext-backend` | Frappe gunicorn |
| `erpnext-websocket` | realtime (socket.io) |
| `erpnext-scheduler` | background scheduler |
| `erpnext-queue-short`, `erpnext-queue-long` | background workers |
| `erpnext-nginx` | ERPNext's own web server (assets + proxy) |
| `platform-api` | control plane API — **`saas` profile only** |
| `platform-ui` | operator console — **`saas` profile only** |

Named volumes: `sites`, `logs`, `db-data`, `redis-cache-data`,
`redis-queue-data`, `caddy-data`, `caddy-config`, `backend-data` (app SQLite),
`platform-data` (tenant registry, SaaS only).

## Configuration (`.env`)

| Variable | Purpose |
| --- | --- |
| `ERPNEXT_VERSION` | ERPNext image tag (default `v15`; this project targets `v16`) |
| `SITE_NAME` | ERPNext site (default `equimed.local`) |
| `ADMIN_PASSWORD` | ERPNext Administrator password |
| `DB_ROOT_PASSWORD` | MariaDB root password |
| `JWT_SECRET_KEY` | **change in production** — signs app JWTs |
| `FIRST_ADMIN_EMAIL` / `_PASSWORD` / `_NAME` | app Administrator seeded on first backend boot |
| `ERPNEXT_API_KEY` / `_SECRET` | backend→ERPNext auth (User → Settings → API Access) |
| `HTTP_PORT` / `HTTPS_PORT` / `ERPNEXT_PORT` | published ports (default 80 / 443 / 8080) |
| `TENANCY_MODE` | `single` (default) or `multi` |
| `CADDYFILE` | `Caddyfile` (default) or `Caddyfile.saas` |

### SaaS plane only

| Variable | Purpose |
| --- | --- |
| `INTERNAL_API_TOKEN` | shared secret for control plane ↔ tenant app. Unset = both refuse every internal call |
| `PLATFORM_JWT_SECRET_KEY` | signs **operator** sessions. Never reuse `JWT_SECRET_KEY` |
| `SECRET_ENCRYPTION_KEY` | encrypts tenant ERPNext credentials at rest in the registry |
| `FIRST_OWNER_EMAIL` / `_PASSWORD` / `_NAME` | first platform operator, seeded on first control-plane boot |
| `BASE_DOMAIN` | host suffix for tenant subdomains (`acme.equimed.app`) |
| `PLATFORM_DOMAIN` | operator console hostname |
| `PROVISIONER` | `noop` (default) or `bench` — see the warning in [multi-tenancy.md](multi-tenancy.md) |

Generate each secret with `openssl rand -hex 32`. They must be different values.

## First-run ERPNext setup

1. Log into ERPNext (`:8080`) and complete the setup wizard (Company = e.g.
   *EquiMed SA*, Country = Cameroon, Currency = XAF, Chart = SYSCOHADA).
2. Generate API keys for the backend user → put them in `.env`
   (`ERPNEXT_API_KEY` / `ERPNEXT_API_SECRET`) → `docker compose up -d backend`.
3. **Create the Custom Fields** the modules rely on (see `docs/api.md` →
   *ERPNext custom fields*) on Customer, Supplier, Item, Serial No and
   Maintenance Visit DocTypes.

## Production deployment

Use the **production overlay** rather than the base file alone:

```bash
# In .env — so the flags cannot be forgotten:
COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml

docker compose up -d --build                 # single-tenant
docker compose --profile saas up -d --build  # SaaS plane
```

Requires **Compose v2.24+** — the overlay uses the `!override` merge tag.

What `docker-compose.prod.yml` changes:

| | Base file | Production overlay |
| --- | --- | --- |
| Secrets | weak defaults (`admin`, `CHANGE_ME`) | **required** — compose refuses to start without them |
| ERPNext desk | published on `:8080` | unpublished; reachable only via Caddy |
| CORS | `["*"]` | must be set to real origins |
| Restart policy | `unless-stopped` | `always` (survives host reboot) |
| Logs | unbounded | rotated at 10 MB × 3 |
| Memory | unbounded | per-service limits |
| Health checks | ERPNext only | + backend and control plane |
| Caddy | `${HTTP_PORT}` | `:80`, `:443`, `:443/udp` (ACME + HTTP/3) |

The failure-loudly behaviour is the point. A missing secret produces:

```
required variable JWT_SECRET_KEY is missing a value:
  set JWT_SECRET_KEY (openssl rand -hex 32)
```

rather than a stack that boots on `CHANGE_ME_IN_PRODUCTION` and looks fine.

> **Why `!override` matters.** Compose *appends* to list fields such as `ports`
> when merging files, so a plain `ports: []` is silently a no-op and the ERPNext
> desk stays exposed. The overlay uses `ports: !override []`. If you ever
> downgrade Compose below 2.24, check `docker compose config` and confirm
> `erpnext-nginx` has no published port before exposing the host.

### Before first boot on a public host

```bash
for v in JWT_SECRET_KEY SECRET_ENCRYPTION_KEY PLATFORM_JWT_SECRET_KEY INTERNAL_API_TOKEN; do
  echo "$v=$(openssl rand -hex 32)"
done   # paste into .env — they must all differ
```

- [ ] Point DNS at the host; set the real domain in `caddy/Caddyfile`
      (single-tenant) or `BASE_DOMAIN` + `PLATFORM_DOMAIN` (SaaS).
- [ ] Firewall: allow 80/443 only. Nothing else needs to be reachable.
- [ ] Change `ADMIN_PASSWORD` (ERPNext) and `FIRST_ADMIN_PASSWORD`, then log in
      once and change them again from the UI.
- [ ] `docker compose config | grep -c published` — expect only Caddy's ports.
- [ ] Schedule `scripts/backup.sh` and copy backups **off** the host.

### Known constraint: SQLite

The app database is still SQLite on a volume. That is fine for a single-tenant
install and for a SaaS pilot, but SQLite serialises writes, so it will become
the bottleneck — and a risk — under real multi-tenant load. Moving
`DATABASE_URL` to PostgreSQL is the next infrastructure step; it needs a driver
added and Alembic introduced first (see the note below).

## Production notes

- **HTTPS (single-tenant):** replace `:80` in `caddy/Caddyfile` with your real
  domain (`erp.example.com { reverse_proxy … }`); Caddy provisions a certificate
  automatically. Point DNS at the host.
- **HTTPS (SaaS):** use `Caddyfile.saas`. Certificates are issued on demand and
  gated by the control plane's `/internal/tls/check`, so a customer's own domain
  works as soon as they CNAME it — and pointing DNS at you is *not* enough to
  make you request a certificate. Point `*.${BASE_DOMAIN}` and
  `${PLATFORM_DOMAIN}` at the host.
- **Never expose `/internal`** (on either service) through the public proxy.
- **Secrets:** set a strong `JWT_SECRET_KEY`, `ADMIN_PASSWORD`,
  `DB_ROOT_PASSWORD`, and change the seeded `FIRST_ADMIN_PASSWORD` after first
  login. `.env` is git-ignored.
- **App database:** the FastAPI auth store is SQLite by default. For production
  point `DATABASE_URL` at a managed DB and introduce Alembic migrations before
  schema changes (currently `create_all` on startup).
- **ERPNext version:** the project targets v16; pin `ERPNEXT_VERSION` to a
  verified tag.

## Backups

```bash
./scripts/backup.sh           # writes into the sites volume: sites/<site>/private/backups
```

In `single` mode this backs up `SITE_NAME`. In `multi` mode it **enumerates every
site on the bench**, so onboarding a customer cannot silently leave them out of
the rotation.

Schedule via host cron, e.g. `0 2 * * * /path/to/Equimed/scripts/backup.sh`.
Also snapshot the Docker volumes (`db-data`, `sites`, `backend-data`, and
`platform-data` on the SaaS plane) — a backup on the same disk is not a backup.

## Operations

```bash
docker compose ps                     # status
docker compose logs -f backend        # tail a service
docker compose up -d --build backend  # rebuild + restart one service
docker compose down                   # stop (keep volumes/data)
docker compose down -v                # stop and DELETE all data
```

## Tests

```bash
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && pytest        # 150 tests, no live ERPNext needed
cd ../frontend && npm install && npm run build   # type-check + production build

# Control plane (SaaS plane only)
cd ../platform/api && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && pytest        # 34 tests
cd ../ui && npm install && npm run build
```
