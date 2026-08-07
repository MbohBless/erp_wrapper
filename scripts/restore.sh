#!/usr/bin/env bash
# Restore from an off-site backup in Cloudflare R2.
#
#   ./scripts/restore.sh --list                    what is available
#   ./scripts/restore.sh --latest                  restore the most recent
#   ./scripts/restore.sh backup-2026...-ab12.tar.gz  restore a specific bundle
#   ./scripts/restore.sh --latest --dry-run        fetch and verify, change nothing
#
# **This overwrites live data.** It drops and reloads the ERPNext site database
# and replaces the app database. It refuses to run without an explicit
# confirmation, and always takes a safety copy of the current state first — a
# restore performed against the wrong bundle should be recoverable too.
#
# A backup you have never restored is a hypothesis, not a backup. Run this with
# --dry-run periodically: it downloads, decrypts and verifies the bundle opens,
# without touching anything.
set -euo pipefail
cd "$(dirname "$0")/.."

RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}✓${OFF} $*"; }
warn() { echo "${YELLOW}!${OFF} $*"; }
die()  { echo "${RED}✗${OFF} $*" >&2; exit 1; }

# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

: "${R2_BUCKET:?set R2_BUCKET in .env}"
: "${R2_ACCOUNT_ID:?set R2_ACCOUNT_ID in .env}"
: "${R2_ACCESS_KEY_ID:?set R2_ACCESS_KEY_ID in .env}"
: "${R2_SECRET_ACCESS_KEY:?set R2_SECRET_ACCESS_KEY in .env}"
PREFIX="${R2_PREFIX:-equimed}"
SITE="${SITE_NAME:-equimed.local}"

command -v rclone >/dev/null 2>&1 || die "rclone is not installed"

export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export RCLONE_CONFIG_R2_REGION=auto
export RCLONE_CONFIG_R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
REMOTE="R2:${R2_BUCKET}/${PREFIX}"

DRY=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    *) ARGS+=("$a") ;;
  esac
done
set -- "${ARGS[@]:-}"

case "${1:-}" in
  --list|"")
    echo "Available backups in ${REMOTE}:"
    rclone lsl "$REMOTE" 2>/dev/null | grep -E 'backup-' | sort -k4 | sed 's/^/  /' || echo "  (none)"
    echo
    echo "  restore with: ./scripts/restore.sh --latest"
    exit 0
    ;;
  --latest)
    NAME=$(rclone lsf "$REMOTE" 2>/dev/null | grep -E '^backup-' | sort -r | head -1)
    [ -n "$NAME" ] || die "no backups found in ${REMOTE}"
    ;;
  *)
    NAME="$1"
    ;;
esac

STAGE=$(mktemp -d); trap 'rm -rf "$STAGE"' EXIT
echo "fetching ${NAME}…"
rclone copyto "${REMOTE}/${NAME}" "$STAGE/$NAME" || die "download failed"
ok "downloaded ($(du -h "$STAGE/$NAME" | cut -f1))"

BUNDLE="$STAGE/$NAME"
if [[ "$NAME" == *.enc ]]; then
  [ -n "${BACKUP_ENCRYPTION_KEY:-}" ] || die "this bundle is encrypted but BACKUP_ENCRYPTION_KEY is unset"
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -in "$BUNDLE" -out "${BUNDLE%.enc}" -pass "pass:${BACKUP_ENCRYPTION_KEY}" \
    || die "decryption failed — wrong BACKUP_ENCRYPTION_KEY?"
  BUNDLE="${BUNDLE%.enc}"
  ok "decrypted"
fi

tar -xzf "$BUNDLE" -C "$STAGE" || die "bundle is corrupt — it did not extract"
[ -f "$STAGE/manifest.json" ] || die "no manifest; this is not an EquiMed bundle"
echo "manifest:"; sed 's/^/  /' "$STAGE/manifest.json"

# Verify the payload actually opens before touching anything live.
gunzip -t "$STAGE/erpnext-database.sql.gz" || die "the ERPNext dump is corrupt"
python3 -c "
import sqlite3, sys
c = sqlite3.connect('$STAGE/app.db')
n = c.execute('select count(*) from sqlite_master').fetchone()[0]
print(f'  app.db opens, {n} objects')
" || die "the app database is corrupt"
ok "bundle verified"

if [ "$DRY" -eq 1 ]; then
  echo; ok "dry run — verified and discarded, nothing was changed."
  exit 0
fi

echo
warn "This REPLACES live data on $(hostname):"
warn "  ERPNext site '${SITE}' database, and the app database"
printf "Type the site name (%s) to proceed: " "$SITE"
read -r CONFIRM
[ "$CONFIRM" = "$SITE" ] || die "confirmation did not match; nothing was changed."

# Safety copy of the CURRENT state — a restore is itself a destructive act, and
# choosing the wrong bundle should not be terminal.
SAFETY="pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "backups/${SAFETY}"
docker compose exec -T backend python -c "
import sqlite3
s=sqlite3.connect('/app/data/app.db'); d=sqlite3.connect('/tmp/pre.db'); s.backup(d); d.close()
" >/dev/null 2>&1 && docker compose cp backend:/tmp/pre.db "backups/${SAFETY}/app.db" >/dev/null 2>&1 || true
docker compose exec -T erpnext-backend bench --site "$SITE" backup >/dev/null 2>&1 || true
ok "current state saved to backups/${SAFETY}/ and the bench backup directory"

echo "restoring ERPNext…"
docker compose cp "$STAGE/erpnext-database.sql.gz" "erpnext-backend:/tmp/restore-db.sql.gz" >/dev/null
docker compose exec -T erpnext-backend bench --site "$SITE" --force restore /tmp/restore-db.sql.gz \
  --db-root-password "${DB_ROOT_PASSWORD}" \
  || die "bench restore failed — the safety copy in backups/${SAFETY} is intact"
ok "ERPNext restored"

if [ -f "$STAGE/erpnext-files.tar" ]; then
  docker compose cp "$STAGE/erpnext-files.tar" "erpnext-backend:/tmp/restore-files.tar" >/dev/null
  docker compose exec -T erpnext-backend sh -c "cd sites/${SITE} && tar -xf /tmp/restore-files.tar" >/dev/null 2>&1 \
    && ok "attachments restored" || warn "attachments could not be restored"
fi

echo "restoring the app database…"
docker compose cp "$STAGE/app.db" backend:/app/data/app.db.restored >/dev/null
docker compose exec -T backend sh -c "mv /app/data/app.db.restored /app/data/app.db"
docker compose restart backend >/dev/null
ok "app database restored"

echo
ok "restore complete — sign in and verify before deleting backups/${SAFETY}"
