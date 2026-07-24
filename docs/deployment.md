# EquiMed — Deployment

Everything runs via **Docker Compose** on a single VPS. Caddy is the only public
entry point (port 80).

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
| `caddy` | public reverse proxy (`:80`): `/`→frontend, `/api/*`→backend, `erp.localhost`→ERPNext |
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

Named volumes: `sites`, `logs`, `db-data`, `redis-cache-data`,
`redis-queue-data`, `caddy-data`, `caddy-config`, `backend-data` (app SQLite).

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
| `HTTP_PORT` / `ERPNEXT_PORT` | published ports (default 80 / 8080) |

## First-run ERPNext setup

1. Log into ERPNext (`:8080`) and complete the setup wizard (Company = e.g.
   *EquiMed SA*, Country = Cameroon, Currency = XAF, Chart = SYSCOHADA).
2. Generate API keys for the backend user → put them in `.env`
   (`ERPNEXT_API_KEY` / `ERPNEXT_API_SECRET`) → `docker compose up -d backend`.
3. **Create the Custom Fields** the modules rely on (see `docs/api.md` →
   *ERPNext custom fields*) on Customer, Supplier, Item, Serial No and
   Maintenance Visit DocTypes.

## Production notes

- **HTTPS:** replace `:80` in `caddy/Caddyfile` with your real domain
  (`erp.example.com { reverse_proxy … }`); Caddy provisions a certificate
  automatically. Point DNS at the host.
- **Secrets:** set a strong `JWT_SECRET_KEY`, `ADMIN_PASSWORD`,
  `DB_ROOT_PASSWORD`, and change the seeded `FIRST_ADMIN_PASSWORD` after first
  login. `.env` is git-ignored.
- **App database:** the FastAPI auth store is SQLite by default. For production
  point `DATABASE_URL` at a managed DB and introduce Alembic migrations before
  schema changes (currently `create_all` on startup).
- **ERPNext version:** the project targets v16; pin `ERPNEXT_VERSION` to a
  verified tag.

## Backups

Nightly ERPNext DB + files backup:

```bash
./scripts/backup.sh           # writes into the sites volume: sites/<site>/private/backups
```

Schedule via host cron, e.g. `0 2 * * * /path/to/Equimed/scripts/backup.sh`.
Also snapshot the Docker volumes (`db-data`, `sites`, `backend-data`).

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
pip install -r requirements.txt && pytest        # 105 tests, no live ERPNext needed
cd ../frontend && npm install && npm run build   # type-check + production build
```
