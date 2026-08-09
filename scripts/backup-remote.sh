#!/usr/bin/env bash
# Off-site backup to Cloudflare R2, with content de-duplication and retention.
#
#   ./scripts/backup-remote.sh            # back up and sync if anything changed
#   ./scripts/backup-remote.sh --force    # upload even if nothing changed
#   ./scripts/backup-remote.sh --list     # what is currently stored off-site
#
# Why R2: egress is free. A restore happens on the worst day you will have, and
# paying per gigabyte to retrieve your own data during an outage is a bad
# incentive. Ten backups of this stack also fit inside R2's permanent free tier.
#
# What goes in a bundle:
#   erpnext-database.sql.gz   the ledger, stock, customers — the irreplaceable part
#   erpnext-files.tar         attachments and uploads
#   app.db                    users, branding, budgets, and (once payments ship)
#                             payment reconciliation state, which cannot be
#                             reconstructed from ERPNext alone
#   manifest.json             what this bundle is, and the hash it was keyed on
#
# NOT included: .env. Those secrets should live in a password manager, not in
# the same bucket as the data they protect.
set -euo pipefail
cd "$(dirname "$0")/.."

RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}✓${OFF} $*"; }
warn() { echo "${YELLOW}!${OFF} $*"; }

# A failed backup is the failure you find out about last — when you need a
# restore. Say so at the time, in the same channel as everything else.
alert() {
  local hook
  hook="${ALERT_WEBHOOK_URL:-$(env_get ALERT_WEBHOOK_URL 2>/dev/null)}"
  [ -n "$hook" ] || return 0
  local text=":rotating_light: *EquiMed backup FAILED on $(hostname)*\n$1"
  local payload
  case "$hook" in
    *discord.com*|*discordapp.com*)
      payload=$(python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1]}))' "$text") ;;
    *)
      payload=$(python3 -c 'import json,sys; print(json.dumps({"text": sys.argv[1]}))' "$text") ;;
  esac
  curl -sS -m 15 -X POST -H 'Content-Type: application/json' -d "$payload" "$hook" >/dev/null 2>&1 || true
}

die()  { echo "${RED}✗${OFF} $*" >&2; alert "$*"; exit 1; }

# .env is a key/value file, not a shell script. Sourcing it EXECUTES it, so a
# value like `Biomedical Equipment & Supplies` backgrounds a process and tries
# to run "Equipment" — and a hostile value would simply run. Read the specific
# keys we need instead, stripping surrounding quotes, with no evaluation.
env_get() {
  [ -f .env ] || return 0
  local v
  v=$(sed -nE "s/^$1=(.*)$/\1/p" .env | tail -1)
  # Strip one layer of surrounding quotes with parameter expansion rather than
  # a second sed — nesting sed escapes inside shell quoting is how the first
  # attempt silently returned the literal "\1".
  case "$v" in
    \"*\") v=${v#\"}; v=${v%\"} ;;
    \'*\') v=${v#\'}; v=${v%\'} ;;
  esac
  printf '%s' "$v"
}

R2_BUCKET="${R2_BUCKET:-$(env_get R2_BUCKET)}"
R2_ACCOUNT_ID="${R2_ACCOUNT_ID:-$(env_get R2_ACCOUNT_ID)}"
R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:-$(env_get R2_ACCESS_KEY_ID)}"
R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:-$(env_get R2_SECRET_ACCESS_KEY)}"
R2_PREFIX="${R2_PREFIX:-$(env_get R2_PREFIX)}"
BACKUP_KEEP="${BACKUP_KEEP:-$(env_get BACKUP_KEEP)}"
BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-$(env_get BACKUP_ENCRYPTION_KEY)}"
SITE_NAME="${SITE_NAME:-$(env_get SITE_NAME)}"

: "${R2_BUCKET:?set R2_BUCKET in .env}"
: "${R2_ACCOUNT_ID:?set R2_ACCOUNT_ID in .env}"
: "${R2_ACCESS_KEY_ID:?set R2_ACCESS_KEY_ID in .env}"
: "${R2_SECRET_ACCESS_KEY:?set R2_SECRET_ACCESS_KEY in .env}"
KEEP="${BACKUP_KEEP:-10}"
PREFIX="${R2_PREFIX:-equimed}"

command -v rclone >/dev/null 2>&1 || die "rclone is not installed (see docs/deployment.md)"

# rclone config is generated per run from .env rather than kept on disk, so the
# credentials live in exactly one place.
export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export RCLONE_CONFIG_R2_REGION=auto
export RCLONE_CONFIG_R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
# R2 does not implement multipart ETags the way rclone expects for checksums.
export RCLONE_S3_NO_CHECK_BUCKET=true

REMOTE="R2:${R2_BUCKET}/${PREFIX}"

case "${1:-}" in
  --list)
    echo "Backups in ${REMOTE}:"
    rclone lsl "$REMOTE" 2>/dev/null | sort -k4 | sed 's/^/  /' || echo "  (none)"
    exit 0
    ;;
esac

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

SITE="${SITE_NAME:-equimed.local}"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

# --- 1. ERPNext ------------------------------------------------------------
echo "taking an ERPNext backup…"
docker compose exec -T erpnext-backend bench --site "$SITE" backup --with-files >/dev/null 2>&1 \
  || die "bench backup failed for '$SITE'"

# bench writes into the site's private/backups; take the newest of each kind.
#
# The path must be ABSOLUTE. `bench` reports paths relative to its working
# directory, but `docker compose cp` resolves against the container root, so a
# relative path fails with "could not find the file".
BENCH_ROOT=$(docker compose exec -T erpnext-backend sh -c 'pwd' | tr -d '\r')
BDIR="${BENCH_ROOT}/sites/${SITE}/private/backups"
newest() { docker compose exec -T erpnext-backend sh -c "ls -1t ${BDIR}/*${1} 2>/dev/null | head -1" | tr -d '\r'; }
DB_REMOTE=$(newest "database.sql.gz")
[ -n "$DB_REMOTE" ] || die "no database dump produced"
FILES_REMOTE=$(newest "files.tar")

docker compose cp "erpnext-backend:${DB_REMOTE}" "$STAGE/erpnext-database.sql.gz" >/dev/null
[ -n "$FILES_REMOTE" ] && docker compose cp "erpnext-backend:${FILES_REMOTE}" "$STAGE/erpnext-files.tar" >/dev/null 2>&1 || true
ok "ERPNext dump captured"

# --- 2. App database -------------------------------------------------------
# SQLite's online backup API, not `cp`: copying the file under a live writer
# can capture a torn page and produce a backup that will not open.
echo "copying the app database…"
docker compose exec -T backend python -c "
import sqlite3
src = sqlite3.connect('/app/data/app.db')
dst = sqlite3.connect('/tmp/app-backup.db')
src.backup(dst); dst.close(); src.close()
" >/dev/null 2>&1 || die "app database backup failed"
docker compose cp backend:/tmp/app-backup.db "$STAGE/app.db" >/dev/null
docker compose exec -T backend rm -f /tmp/app-backup.db >/dev/null 2>&1 || true
ok "app database captured"

# --- 3. Content hash -------------------------------------------------------
# The dump differs on every run even when nobody has touched the system:
# gzip stores a timestamp, mysqldump writes a "Dump completed on" line, and
# ERPNext's scheduler continuously appends to its own bookkeeping tables.
# Measured on this stack: two dumps 5 minutes apart with the app idle differed
# only in `tabScheduled Job Log` (a row per tick) and `tabScheduled Job Type`
# (last_execution timestamps).
#
# Hashing that would mean "changed" forever and the de-duplication would never
# fire. So the hash ignores those tables — they are still IN the backup, they
# just do not count as a change. Anything a user did lands elsewhere.
NOISY_TABLES='tabScheduled Job Log|tabScheduled Job Type|tabError Log|tabActivity Log|tabSessions|tabError Snapshot'

# mysqldump writes extended INSERTs that wrap across lines, so filtering by
# line content alone would keep the continuations. Track the current table
# from the section header and drop the whole block instead.
strip_noise() {
  awk -v noisy="$NOISY_TABLES" '
    /^-- Dumping data for table/ {
      # Split on the backtick rather than sub(/^.*`/) — `.*` is greedy and
      # matches through the LAST backtick, yielding an empty table name and a
      # filter that silently passes everything. That bug shipped once already.
      n = split($0, a, "`")
      tbl = (n >= 2 ? a[2] : "")
      skip = (tbl ~ "^(" noisy ")$")
    }
    !skip
  '
}

CONTENT_HASH=$(
  {
    gunzip -c "$STAGE/erpnext-database.sql.gz" \
      | grep -avE '^-- (Dump completed|Server version|Host:)' \
      | strip_noise \
      | sha256sum | cut -d' ' -f1
    sha256sum "$STAGE/app.db" | cut -d' ' -f1
  } | sha256sum | cut -d' ' -f1
)
SHORT=${CONTENT_HASH:0:12}

LAST=$(rclone cat "${REMOTE}/latest.hash" 2>/dev/null || echo "")
if [ "$FORCE" -eq 0 ] && [ "$LAST" = "$CONTENT_HASH" ]; then
  ok "no change since the last backup (${SHORT}) — nothing uploaded"
  exit 0
fi

# --- 4. Bundle -------------------------------------------------------------
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
NAME="backup-${STAMP}-${SHORT}.tar.gz"

cat > "$STAGE/manifest.json" <<JSON
{
  "created_utc": "${STAMP}",
  "content_sha256": "${CONTENT_HASH}",
  "erpnext_site": "${SITE}",
  "host": "$(hostname)",
  "contents": ["erpnext-database.sql.gz", "erpnext-files.tar", "app.db"]
}
JSON

tar -czf "$STAGE/$NAME" -C "$STAGE" \
  manifest.json erpnext-database.sql.gz app.db \
  $([ -f "$STAGE/erpnext-files.tar" ] && echo erpnext-files.tar)

SIZE=$(du -h "$STAGE/$NAME" | cut -f1)

# --- 5. Encrypt (optional but strongly advised) ----------------------------
# This bundle is the customer's complete accounting record. Encrypting before
# it leaves the machine means a bucket misconfiguration is not a data breach.
UPLOAD="$STAGE/$NAME"
if [ -n "${BACKUP_ENCRYPTION_KEY:-}" ]; then
  openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
    -in "$STAGE/$NAME" -out "$STAGE/${NAME}.enc" -pass "pass:${BACKUP_ENCRYPTION_KEY}"
  UPLOAD="$STAGE/${NAME}.enc"; NAME="${NAME}.enc"
  ok "bundle encrypted (AES-256)"
else
  warn "BACKUP_ENCRYPTION_KEY is unset — uploading UNENCRYPTED accounting data"
fi

# --- 6. Upload + retention -------------------------------------------------
echo "uploading ${NAME} (${SIZE})…"
rclone copyto "$UPLOAD" "${REMOTE}/${NAME}" --s3-no-check-bucket || die "upload failed"
# copyto from a file, not rcat: rcat streams from stdin and R2 answers that
# with 501 Not Implemented.
printf '%s' "$CONTENT_HASH" > "$STAGE/latest.hash"
rclone copyto "$STAGE/latest.hash" "${REMOTE}/latest.hash" --s3-no-check-bucket
ok "uploaded"

# Keep the newest KEEP bundles. Names sort chronologically because the
# timestamp is fixed-width and leads the filename.
mapfile -t OLD < <(rclone lsf "$REMOTE" 2>/dev/null | grep -E '^backup-' | sort -r | tail -n +$((KEEP + 1)))
for f in "${OLD[@]:-}"; do
  [ -n "$f" ] || continue
  rclone deletefile "${REMOTE}/${f}" >/dev/null 2>&1 && echo "  pruned ${f}"
done

COUNT=$(rclone lsf "$REMOTE" 2>/dev/null | grep -c '^backup-' || echo 0)
ok "off-site backups retained: ${COUNT}/${KEEP}"
