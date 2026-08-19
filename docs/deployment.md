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
| `ACCESS_TOKEN_EXPIRE_MINUTES` | access-token lifetime (default 60) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | session lifetime (default 30) |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` (use `text` for local dev) |
| `CADDYFILE` | `Caddyfile` (default) or `Caddyfile.saas` |
| `DISABLED_ROLES` | roles this workspace does not hand out, e.g. `["Sales"]` |

**`DISABLED_ROLES`** retires a role for *this deployment* without removing it
from the product — one workspace having no sales reps is no reason for the next
to lose the option. A retired role cannot be assigned (422 on user create and on
update, not merely hidden in the dropdown), but keeps its permissions and its
tests, so re-enabling it is an edit to this file rather than a restoration.
Administrator is never retirable: a deployment that disabled it could lock
itself out of its own user administration.

Retiring a role does **not** change what the remaining roles may do. Who can
reach what is the product's RBAC matrix, in [api.md](api.md).

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

1b. **Run `scripts/configure_company_accounts.py`.** The wizard builds the chart
   of accounts but does not reliably set the company's *default* accounts, and
   the ones it guesses are matched by account-number prefix, which on SYSCOHADA
   picks semantically wrong ones — the receivable control came out as
   `4186-Clients, intérêts courus` (accrued interest) instead of `4111-Clients`.

   ```bash
   docker compose cp scripts/configure_company_accounts.py erpnext-backend:/tmp/cfg.py
   echo 'exec(open("/tmp/cfg.py").read())' \
     | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console
   ```

   Until this runs, the instance **cannot post**: a purchase invoice fails on a
   missing Round Off Account, a goods receipt on a missing Stock Adjustment
   Account, and a cash receipt demands a bank reference because no Mode of
   Payment has an account. The quieter problem is worse — with the wrong
   receivable control every customer invoice posts to an accrued-interest
   account, and nothing complains until an audit.

   > Pipe a single `exec(open(...).read())` line rather than redirecting the
   > file into `bench console`. The console hands stdin to IPython, which splits
   > it into cells and dedents function bodies, so a multi-line script raises
   > `NameError` on its own helpers.

   The account choices are conventional SYSCOHADA defaults for a distribution
   business. **Have the client's accountant confirm them before real
   transactions are posted** — the script restores a working configuration, it
   does not give accounting advice.
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
- [ ] Schedule `scripts/backup-remote.sh` (off-site to R2) and store `BACKUP_ENCRYPTION_KEY` in a password manager.
- [ ] Rehearse a restore with `scripts/restore.sh --latest --dry-run`.

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

Also snapshot the Docker volumes (`db-data`, `sites`, `backend-data`, and
`platform-data` on the SaaS plane) — a backup on the same disk is not a backup.

### Off-site backups (Cloudflare R2)

`scripts/backup-remote.sh` bundles the ERPNext dump, attachments and the app
database, encrypts the bundle, and uploads it to R2.

```bash
./scripts/backup-remote.sh            # back up if anything changed
./scripts/backup-remote.sh --force    # upload regardless
./scripts/backup-remote.sh --list     # what is stored off-site
```

Required in `.env`: `R2_BUCKET`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY`, `BACKUP_ENCRYPTION_KEY`. Optional: `R2_PREFIX`
(default `equimed`), `BACKUP_KEEP` (default 10). Needs rclone **1.59+** —
distro packages are often older and fail with `501 Not Implemented`, because
R2 does not support the streaming upload older versions use.

**`BACKUP_ENCRYPTION_KEY` is not recoverable.** Bundles are encrypted before
they leave the host, so losing the key loses every backup. Store it in a
password manager, not only on the server. `.env` is deliberately *not* included
in the bundle: secrets do not belong in the same bucket as the data they
protect.

**Change detection.** Uploads are skipped when nothing has changed, keyed on a
hash of the dump. The hash deliberately ignores `tabScheduled Job Log`,
`tabScheduled Job Type` and the error/activity/session tables: ERPNext's
scheduler writes to them continuously, so including them means the backup
"changed" on every run and de-duplication never fires. Those tables are still
present in the backup — they just do not count as a change.

### Restoring

```bash
./scripts/restore.sh --list                 # what is available
./scripts/restore.sh --latest --dry-run     # verify a bundle, change nothing
./scripts/restore.sh --latest               # restore (destructive; asks to confirm)
```

A restore drops and reloads the site database, so it requires typing the site
name and takes a safety copy of the current state first.

Verify the restore path rather than assuming it: load a bundle into a scratch
database and compare row counts against live.

```bash
gunzip -c erpnext-database.sql.gz | mariadb -uroot -p"$DB_ROOT_PASSWORD" verify_restore
```

### Demo data, and getting back to a clean instance

`scripts/seed_demo.py` populates a realistic dataset — five users (one per
role), suppliers, customers, catalogue, stock, invoices spread across the
dashboard's 30-day trend window, receipts, installed equipment and maintenance
visits.

```bash
# From inside the backend container: no Cloudflare in the path, so a failing
# document returns ITS OWN error rather than an edge 502 error page.
docker compose cp scripts/seed_demo.py backend:/tmp/seed_demo.py
docker compose exec -T backend python /tmp/seed_demo.py \
  --base http://localhost:8000 \
  --admin-email "$FIRST_ADMIN_EMAIL" --admin-password "$FIRST_ADMIN_PASSWORD"
```

It refuses to run if the instance already holds invoices or customers, unless
`--force`. That guard matters: seeding onto a real ledger is not undone by
deleting rows, because stock and GL entries fan out across doctypes.

**The reset is a restore, not a delete.** ERPNext submitted documents cannot
simply be removed, so the supported path back is a snapshot taken *before*
seeding:

```bash
./scripts/backup-remote.sh --force        # then copy the newest bundle to a
                                          # name not starting with "backup-",
                                          # so retention never prunes it
./scripts/restore.sh pristine-configured.tar.gz.enc
```

Retention only sweeps objects named `backup-*`, so a `pristine-*` object
survives indefinitely. Keep one baseline that is **clean and already
configured** — restoring a snapshot taken before
`configure_company_accounts.py` hands back an instance that cannot post.

### Alerting when something breaks

`scripts/watchdog.sh` checks the stack every five minutes and posts to Slack or
Discord when something is wrong. Set one webhook in `.env`; the format is
detected from the URL, so either works:

```bash
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/...     # or discord.com/api/webhooks/...
ALERT_SITE_URL=https://app.example.com/api/health
sudo ./scripts/install-watchdog.sh
./scripts/watchdog.sh --test      # prove the webhook works
./scripts/watchdog.sh --status    # what it sees right now, notifying nobody
```

Checks: containers running and healthy, the API answering over TLS, disk under
85%, memory headroom, **the newest off-site backup under 36h old**, and the
certificate more than 14 days from expiry. `scripts/backup-remote.sh` posts to
the same webhook when a backup fails.

It notifies on *transitions*, then hourly while a problem persists, and once on
recovery. Alerting every five minutes trains you to mute the channel, and the
alert that matters then arrives somewhere muted.

A systemd timer rather than cron: it starts after Docker, so a reboot does not
fire an outage alert while the stack is still coming up.

> **This cannot tell you the host died.** Nothing running on the host can.
> Pair it with an external check — UptimeRobot, Better Stack and Healthchecks.io
> all have free tiers that post to the same webhook. The watchdog covers "a part
> of the system is unhealthy"; the external check covers "the machine is gone".

### Scheduling

```cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
30 2 * * * flock -n /var/lock/equimed-backup.lock /opt/equimed/scripts/backup-remote.sh >> /var/log/equimed-backup.log 2>&1
30 3 * * 0 flock -n /var/lock/equimed-backup.lock /opt/equimed/scripts/restore.sh --latest --dry-run >> /var/log/equimed-backup.log 2>&1
```

Set `PATH` explicitly — cron's default omits `/usr/local/bin`. `flock -n` skips
a run rather than stacking a second dump on one that overran. The weekly
dry-run is a restore rehearsal: a backup nobody has restored is a hypothesis.

Test cron jobs in a stripped environment, not an interactive shell, since that
is where they differ:

```bash
env -i HOME=/root PATH=/usr/sbin:/usr/bin:/sbin:/bin /bin/sh -c '<the cron command>'
```

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
pip install -r requirements.txt && pytest        # 416 tests, no live ERPNext needed
cd ../frontend && npm install && npm run build   # type-check + production build

# Control plane (SaaS plane only)
cd ../platform/api && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && pytest        # 34 tests
cd ../ui && npm install && npm run build
```
