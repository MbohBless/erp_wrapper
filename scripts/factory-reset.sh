#!/usr/bin/env bash
# Destroy everything and return the deployment to a fresh install.
#
#   ./scripts/factory-reset.sh
#
# This is not the restore path. `scripts/restore.sh` puts back a snapshot;
# this ERASES the ERPNext site and the app database so the setup wizard can be
# run again from nothing — which is the only way to change things ERPNext fixes
# at creation, the company abbreviation above all (it is `set_only_once`, so an
# existing site can never move from "TD" to "QBM").
#
# It takes a final backup first regardless of intent. The cost is 30 seconds;
# the alternative is discovering afterwards that something mattered.
set -euo pipefail
cd "$(dirname "$0")/.."

RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; BOLD=$'\033[1m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}✓${OFF} $*"; }
warn() { echo "${YELLOW}!${OFF} $*"; }
die()  { echo "${RED}✗${OFF} $*" >&2; exit 1; }

env_get() {
  [ -f .env ] || return 0
  local v
  v=$(sed -nE "s/^$1=(.*)$/\1/p" .env | tail -1)
  case "$v" in
    \"*\") v=${v#\"}; v=${v%\"} ;;
    \'*\') v=${v#\'}; v=${v%\'} ;;
  esac
  printf '%s' "$v"
}

set_env() {
  local key="$1" val="$2"
  if grep -qE "^#?${key}=" .env; then
    local esc; esc=$(printf '%s' "$val" | sed -e 's/[\/&]/\\&/g')
    sed -i -E "s|^#?${key}=.*|${key}=${esc}|" .env
  else
    case "$val" in
      *[\ \&\|\;\<\>\(\)\$\`]*) printf '%s="%s"\n' "$key" "$val" >> .env ;;
      *) printf '%s=%s\n' "$key" "$val" >> .env ;;
    esac
  fi
}

SITE="$(env_get SITE_NAME)"; SITE="${SITE:-equimed.local}"
DB_ROOT="$(env_get DB_ROOT_PASSWORD)"

NEW_ADMIN_EMAIL="${NEW_ADMIN_EMAIL:-}"
NEW_ADMIN_PASSWORD="${NEW_ADMIN_PASSWORD:-}"

ASSUME_YES=0
[ "${1:-}" = "--yes" ] && ASSUME_YES=1

echo "${BOLD}FACTORY RESET${OFF}"
echo
echo "This will PERMANENTLY DESTROY, on $(hostname):"
echo "  • the ERPNext site '${SITE}' — every customer, invoice, item and ledger entry"
echo "  • the application database — users, branding, audit log, sessions"
echo
echo "It will KEEP: .env secrets, R2 backups, TLS certificates, the firewall."
echo
echo "Current contents:"
docker compose exec -T db sh -c "true" >/dev/null 2>&1 </dev/null && {
  DBN=$(docker compose exec -T erpnext-backend sh -c "cat sites/${SITE}/site_config.json" 2>/dev/null </dev/null \
        | python3 -c 'import sys,json; print(json.load(sys.stdin)["db_name"])' 2>/dev/null || echo "")
  if [ -n "$DBN" ]; then
    CLI=$(docker compose exec -T db sh -c 'command -v mariadb || command -v mysql' </dev/null | tr -d '\r')
    docker compose exec -T db "$CLI" -uroot -p"$DB_ROOT" -N -B "$DBN" -e "
      select concat('  invoices=', (select count(*) from \`tabSales Invoice\`),
                    '  customers=', (select count(*) from tabCustomer),
                    '  items=', (select count(*) from tabItem),
                    '  GL entries=', (select count(*) from \`tabGL Entry\`));" 2>/dev/null </dev/null \
      | grep -v "Using a password" || true
  fi
} || warn "stack not running; cannot show contents"
echo
if [ "$ASSUME_YES" -eq 1 ]; then
  warn "--yes given: skipping confirmation"
else
  printf "Type the site name (%s) to confirm: " "$SITE"
  read -r CONFIRM
  [ "$CONFIRM" = "$SITE" ] || die "confirmation did not match; nothing was changed."
  printf "Type ERASE to confirm again: "
  read -r CONFIRM2
  [ "$CONFIRM2" = "ERASE" ] || die "not confirmed; nothing was changed."
fi

# --- 1. final backup -----------------------------------------------------
echo
echo "taking a final backup before erasing…"
if ./scripts/backup-remote.sh --force >/tmp/final-backup.log 2>&1; then
  ok "final backup uploaded — see /tmp/final-backup.log"
  grep -E "uploaded|retained" /tmp/final-backup.log | tail -2 || true
else
  warn "the final backup FAILED. Read /tmp/final-backup.log before continuing."
  if [ "$ASSUME_YES" -eq 1 ]; then
    die "the final backup failed and --yes was given; refusing to erase blind."
  fi
  printf "Continue erasing anyway? [type YES]: "
  read -r ANY
  [ "$ANY" = "YES" ] || die "stopped; nothing was erased."
fi

# --- 2. drop the ERPNext site -------------------------------------------
echo
echo "dropping the ERPNext site…"
# --force because the site is in use; --no-backup because we just took one.
docker compose exec -T erpnext-backend bench drop-site "$SITE" \
  --db-root-username=root --db-root-password="$DB_ROOT" --force --no-backup \
  >/dev/null 2>&1 </dev/null || warn "bench drop-site reported an error; checking whether it went anyway"

if docker compose exec -T erpnext-backend sh -c "[ -d sites/${SITE} ]" 2>/dev/null </dev/null; then
  warn "the site directory still exists; removing it directly"
  docker compose exec -T erpnext-backend sh -c "rm -rf sites/${SITE}" </dev/null
fi
ok "ERPNext site removed"

# --- 3. wipe the app database -------------------------------------------
echo "wiping the application database…"
docker compose exec -T backend sh -c "rm -f /app/data/app.db /app/data/app.db-wal /app/data/app.db-shm" \
  2>/dev/null </dev/null || warn "could not remove app.db (is the backend running?)"
ok "application database removed"

# --- 4. new credentials, and clear the old site's API keys ---------------
if [ -n "$NEW_ADMIN_EMAIL" ]; then
  set_env FIRST_ADMIN_EMAIL "$NEW_ADMIN_EMAIL"
  ok "FIRST_ADMIN_EMAIL set to ${NEW_ADMIN_EMAIL}"
fi
if [ -n "$NEW_ADMIN_PASSWORD" ]; then
  set_env FIRST_ADMIN_PASSWORD "$NEW_ADMIN_PASSWORD"
  ok "FIRST_ADMIN_PASSWORD set"
fi

# The keys belonged to a user in a database that no longer exists. Leaving them
# would let the backend start and fail every ERPNext call with a confusing 401.
set_env ERPNEXT_API_KEY ""
set_env ERPNEXT_API_SECRET ""
ok "stale ERPNext API keys cleared (regenerate after the wizard)"

# --- 5. recreate ---------------------------------------------------------
echo
echo "recreating the site (this takes several minutes)…"
# --force-recreate matters: the one-shot has already run once and exited, and
# a plain `up` reports it up-to-date rather than running it again — leaving no
# site and no error.
docker compose rm -fs erpnext-create-site >/dev/null 2>&1 || true
docker compose up -d --force-recreate erpnext-create-site >/dev/null 2>&1 || true
for _ in $(seq 1 120); do
  line=$(docker compose ps -a --format json erpnext-create-site 2>/dev/null | head -1 || true)
  case "$line" in
    *'"State":"exited"'*)
      case "$line" in
        *'"ExitCode":0'*) ok "site created" ;;
        *) warn "site creation exited non-zero — docker compose logs erpnext-create-site" ;;
      esac
      break ;;
  esac
  sleep 5
done

docker compose up -d >/dev/null 2>&1
ok "stack restarted"

echo
echo "${BOLD}Reset complete.${OFF} The instance is empty and unconfigured."
echo
echo "Next — follow docs/fresh-install.md:"
echo "  1. ERPNext setup wizard      → company name, abbreviation, country, currency, chart"
echo "  2. scripts/configure_company_accounts.py   (until this runs, nothing can post)"
echo "  3. scripts/install_custom_fields.py"
echo "  4. Generate ERPNext API keys → ERPNEXT_API_KEY / ERPNEXT_API_SECRET in .env"
echo "  5. docker compose up -d backend"
