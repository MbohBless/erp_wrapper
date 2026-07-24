# EquiMed

A lightweight, web-based ERP for **medical-equipment distributors** in Cameroon.
It gives operations staff a clean, purpose-built UI and API for customers,
suppliers, products, inventory, sales, purchases, equipment and maintenance —
while delegating accounting, stock and master data to **ERPNext**.

> **This is not a generic ERP** — it's a medical-distribution management platform
> layered on top of ERPNext.

## Architecture at a glance

```
Users → Caddy → Next.js frontend → FastAPI backend → ERPNext → MariaDB
                                         │                        ↑
                                    SQLite (app auth)      Redis (cache+queue)
```

The frontend never calls ERPNext directly — only FastAPI does, through one
integration module. FastAPI owns authentication/RBAC in its own database;
ERPNext is the system of record for business data. Everything runs on a single
VPS via Docker Compose.

Full detail: **[docs/architecture.md](docs/architecture.md)**.

## Quick start

```bash
cp .env.example .env          # edit secrets (JWT_SECRET_KEY, passwords…)
docker compose up -d --build
docker compose logs -f erpnext-create-site   # first boot creates the ERPNext site
```

- App: `http://localhost/` (sign in with `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD`)
- API docs: `http://localhost/api/docs`
- ERPNext admin: `http://localhost:8080/`

Deployment, configuration, production hardening and backups:
**[docs/deployment.md](docs/deployment.md)**.

## Modules

| Area | UI route | Backing ERPNext DocType |
| --- | --- | --- |
| Dashboard | `/dashboard` | invoices, payments, bins (aggregated) |
| Sales | `/sales` | Sales Invoice |
| Purchases | `/purchases` | Purchase Invoice |
| Customers | `/customers` | Customer |
| Suppliers | `/suppliers` | Supplier |
| Products | `/products` | Item |
| Inventory | `/inventory` | Warehouse, Batch, Bin, Stock Entry |
| Equipment | `/equipment` | Serial No |
| Maintenance | `/maintenance` | Maintenance Visit |
| Finance | `/finance` | invoices + ERPNext P&L / Balance Sheet |
| Reports | `/reports` | stock & finance reports |
| Settings | `/settings` | profile, preferences, **user & role management** |

Roles: Administrator, Manager, Sales, Store Keeper, Accountant, Biomedical
Engineer. Per-endpoint access and payloads:
**[docs/api.md](docs/api.md)**.

## Repository layout

```
backend/     FastAPI service (api / services / repositories / integrations /
             schemas / models / utils); 105 pytest tests
frontend/    Next.js 14 + Tailwind app (EquiMed design); pages + lib + components
caddy/       Caddyfile (public reverse proxy)
scripts/     backup.sh (nightly ERPNext backup)
docs/        api.md · architecture.md · deployment.md · system-design.md ·
             coding_guidelines.md
docker-compose.yml
```

## Development

```bash
# Backend
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest                       # 105 tests (ERPNext faked, SQLite temp DB)
uvicorn main:app --reload    # http://localhost:8000

# Frontend
cd frontend && npm install
npm run dev                  # http://localhost:3000
npm run build                # type-check + production build
```

The backend follows a strict layered architecture — see
[docs/coding_guidelines.md](docs/coding_guidelines.md) and
[docs/architecture.md](docs/architecture.md).

## Documentation

- **[docs/api.md](docs/api.md)** — every endpoint, RBAC matrix, payloads, errors
- **[docs/architecture.md](docs/architecture.md)** — layers, data ownership, ERPNext integration, stack
- **[docs/deployment.md](docs/deployment.md)** — Docker Compose services, config, HTTPS, backups
- **[docs/system-design.md](docs/system-design.md)** — the original V1 design brief

## Status

All modules have working, tested backends and EquiMed-styled frontend pages.
Known follow-ups: the ERPNext Custom Fields the modules rely on must be created
in the target instance (see [docs/api.md](docs/api.md)); the app-auth DB is
SQLite pending a MariaDB + Alembic move for production.
