#!/usr/bin/env bash
# Nightly ERPNext backup (database + files). Run via cron on the host, e.g.:
#   0 2 * * *  /path/to/Equimed/scripts/backup.sh >> /var/log/equimed-backup.log 2>&1
#
# Backups are written inside the `sites` volume under
# sites/<site>/private/backups and can be copied out with `docker cp`.
set -euo pipefail

cd "$(dirname "$0")/.."

SITE="${SITE_NAME:-equimed.local}"

docker compose exec -T erpnext-backend \
  bench --site "$SITE" backup --with-files

echo "Backup complete for site: $SITE"
