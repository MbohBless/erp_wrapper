#!/usr/bin/env bash
# ERPNext backup (database + files).
#
# Single-tenant:  backs up the one site named by SITE_NAME.
# SaaS plane:     backs up every site on the bench, so adding a customer does
#                 not silently leave them out of the rotation. That is the
#                 failure mode worth engineering against — a per-tenant list
#                 maintained by hand goes stale the first busy week.
#
# Run via cron on the host, e.g.:
#   0 2 * * *  /path/to/Equimed/scripts/backup.sh >> /var/log/equimed-backup.log 2>&1
#
# Backups land inside the `sites` volume under sites/<site>/private/backups.
# Copy them off the host — a backup on the same disk is not a backup:
#   docker compose cp erpnext-backend:/home/frappe/frappe-bench/sites ./backups
set -euo pipefail

cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

MODE="${TENANCY_MODE:-single}"
BENCH="docker compose exec -T erpnext-backend"

backup_site() {
  local site="$1"
  echo "--- backing up ${site}"
  if $BENCH bench --site "$site" backup --with-files; then
    echo "    ok: ${site}"
  else
    # Keep going: one broken site must not abort the whole rotation.
    echo "    FAILED: ${site}" >&2
    return 1
  fi
}

failed=0

if [ "$MODE" = "multi" ]; then
  # Enumerate sites from the bench's sites/ directory — no dependency on the
  # control-plane database from a shell script.
  sites="$($BENCH ls -1 sites 2>/dev/null \
    | tr -d '\r' \
    | grep -Ev '^(assets|apps\.txt|common_site_config\.json)$' || true)"

  if [ -z "$sites" ]; then
    echo "No ERPNext sites found on the bench." >&2
    exit 1
  fi

  echo "Backing up all sites (TENANCY_MODE=multi):"
  while IFS= read -r site; do
    [ -z "$site" ] && continue
    backup_site "$site" || failed=$((failed + 1))
  done <<< "$sites"
else
  backup_site "${SITE_NAME:-equimed.local}" || failed=$((failed + 1))
fi

if [ "$failed" -gt 0 ]; then
  echo "Backup finished with ${failed} failure(s)." >&2
  exit 1
fi

echo "Backup complete."
