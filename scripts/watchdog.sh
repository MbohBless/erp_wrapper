#!/usr/bin/env bash
# Health watchdog: notifies Slack or Discord when something is wrong.
#
#   ./scripts/watchdog.sh            # run the checks, notify on a change
#   ./scripts/watchdog.sh --test     # send a test message and exit
#   ./scripts/watchdog.sh --status   # print the current state, notify nothing
#
# Installed as a systemd timer (see scripts/install-watchdog.sh), NOT as a
# container: a watchdog that shares a fate with the thing it watches is not a
# watchdog. It still cannot report the host being dead — nothing running on the
# host can — so pair it with an external uptime check. See docs/deployment.md.
#
# Notifies on *transitions*, not on every run. A check that alerts every five
# minutes while a disk is full trains you to mute the channel, and then the one
# alert that mattered arrives in a muted channel. While something is still
# broken it re-notifies once an hour, so it cannot be quietly forgotten either.
set -uo pipefail   # NOT -e: a failing check is data, not a reason to abort

cd "$(dirname "$0")/.."

STATE_DIR="/var/lib/equimed-watchdog"
STATE_FILE="$STATE_DIR/state"
LAST_NOTIFY_FILE="$STATE_DIR/last-notify"
RENOTIFY_SECONDS=3600

DISK_WARN_PCT=85
MEM_WARN_MB=300
BACKUP_MAX_AGE_HOURS=36
CERT_WARN_DAYS=14

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

WEBHOOK="${ALERT_WEBHOOK_URL:-$(env_get ALERT_WEBHOOK_URL)}"
SITE="${ALERT_SITE_URL:-$(env_get ALERT_SITE_URL)}"
SITE="${SITE:-http://localhost/api/health}"
HOSTNAME_S=$(hostname)

# --- notification ---------------------------------------------------------
notify() {
  local text="$1"
  [ -n "$WEBHOOK" ] || { echo "(no ALERT_WEBHOOK_URL set) $text"; return 0; }

  # Slack and Discord take different field names. Detecting from the URL means
  # one setting works for either, which is the whole ask.
  local payload
  case "$WEBHOOK" in
    *discord.com*|*discordapp.com*)
      payload=$(python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1]}))' "$text") ;;
    *)
      payload=$(python3 -c 'import json,sys; print(json.dumps({"text": sys.argv[1]}))' "$text") ;;
  esac

  curl -sS -m 15 -X POST -H 'Content-Type: application/json' \
    -d "$payload" "$WEBHOOK" >/dev/null \
    || echo "watchdog: could not reach the webhook" >&2
}

# --- checks ---------------------------------------------------------------
# Each appends a human-readable line to FAILURES. Wording matters: this text is
# read on a phone, at night, by someone who has to decide whether to get up.
FAILURES=()

check_containers() {
  local bad
  bad=$(docker compose ps --format '{{.Service}} {{.State}} {{.Status}}' 2>/dev/null \
        | awk '$2 != "running" {print "  - " $0}')
  [ -n "$bad" ] && FAILURES+=("Containers not running:"$'\n'"$bad")

  local unhealthy
  unhealthy=$(docker compose ps --format '{{.Service}} {{.Status}}' 2>/dev/null \
              | grep -i unhealthy | sed 's/^/  - /')
  [ -n "$unhealthy" ] && FAILURES+=("Containers unhealthy:"$'\n'"$unhealthy")
}

check_api() {
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 15 -A 'equimed-watchdog' "$SITE" 2>/dev/null)
  # 200 is healthy; a redirect means Caddy answered, which is also alive.
  case "$code" in
    200|301|302|307|308) : ;;
    *) FAILURES+=("API health check returned ${code:-no response} for $SITE") ;;
  esac
}

check_disk() {
  local pct
  pct=$(df --output=pcent / 2>/dev/null | tail -1 | tr -dc '0-9')
  if [ -n "$pct" ] && [ "$pct" -ge "$DISK_WARN_PCT" ]; then
    FAILURES+=("Disk ${pct}% full on / (threshold ${DISK_WARN_PCT}%)")
  fi
}

check_memory() {
  local avail
  avail=$(free -m 2>/dev/null | awk '/^Mem:/{print $7}')
  if [ -n "$avail" ] && [ "$avail" -lt "$MEM_WARN_MB" ]; then
    FAILURES+=("Only ${avail}MB memory available (threshold ${MEM_WARN_MB}MB)")
  fi
}

check_backup_age() {
  # The failure this exists for: the nightly backup quietly stops working and
  # nobody finds out until a restore is needed. Age is read from the bundles
  # actually in R2, not from whether the script exited zero.
  local bucket account key secret
  bucket=$(env_get R2_BUCKET); account=$(env_get R2_ACCOUNT_ID)
  key=$(env_get R2_ACCESS_KEY_ID); secret=$(env_get R2_SECRET_ACCESS_KEY)
  [ -n "$bucket" ] && [ -n "$key" ] || return 0
  command -v rclone >/dev/null 2>&1 || return 0

  export RCLONE_CONFIG_R2_TYPE=s3 RCLONE_CONFIG_R2_PROVIDER=Cloudflare \
         RCLONE_CONFIG_R2_REGION=auto \
         RCLONE_CONFIG_R2_ACCESS_KEY_ID="$key" \
         RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$secret" \
         RCLONE_CONFIG_R2_ENDPOINT="https://${account}.r2.cloudflarestorage.com"

  local newest age_h
  newest=$(rclone lsl "R2:${bucket}/$(env_get R2_PREFIX || echo equimed)" 2>/dev/null \
           | grep -E 'backup-' | awk '{print $2" "$3}' | sort -r | head -1)
  if [ -z "$newest" ]; then
    FAILURES+=("No off-site backups found in R2")
    return 0
  fi
  local ts now
  ts=$(date -d "${newest%.*}" +%s 2>/dev/null) || return 0
  now=$(date +%s)
  age_h=$(( (now - ts) / 3600 ))
  if [ "$age_h" -gt "$BACKUP_MAX_AGE_HOURS" ]; then
    FAILURES+=("Newest off-site backup is ${age_h}h old (expected under ${BACKUP_MAX_AGE_HOURS}h)")
  fi
}

check_certificate() {
  # Caddy renews automatically; this catches renewal having silently stopped,
  # which is invisible until the browser warning appears.
  local host days
  host=$(printf '%s' "$SITE" | sed -E 's#^https?://##; s#/.*##')
  case "$SITE" in https://*) : ;; *) return 0 ;; esac
  local end
  end=$(echo | timeout 15 openssl s_client -servername "$host" -connect "${host}:443" 2>/dev/null \
        | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  [ -n "$end" ] || return 0
  days=$(( ( $(date -d "$end" +%s) - $(date +%s) ) / 86400 ))
  if [ "$days" -lt "$CERT_WARN_DAYS" ]; then
    FAILURES+=("TLS certificate for $host expires in ${days} day(s)")
  fi
}

# --- run ------------------------------------------------------------------
case "${1:-}" in
  --test)
    notify ":wrench: EquiMed watchdog test from *${HOSTNAME_S}* — alerts are working."
    echo "test notification sent"
    exit 0
    ;;
esac

check_containers
check_api
check_disk
check_memory
check_backup_age
check_certificate

mkdir -p "$STATE_DIR"
PREVIOUS=$(cat "$STATE_FILE" 2>/dev/null || echo "OK")

if [ "${#FAILURES[@]}" -eq 0 ]; then
  CURRENT="OK"
else
  CURRENT="FAIL"
fi

if [ "${1:-}" = "--status" ]; then
  echo "state: $CURRENT"
  printf '%s\n' "${FAILURES[@]:-  (no problems found)}"
  exit 0
fi

now=$(date +%s)
last_notify=$(cat "$LAST_NOTIFY_FILE" 2>/dev/null || echo 0)

if [ "$CURRENT" = "FAIL" ]; then
  # Notify on the transition, then at most hourly while it is still broken.
  if [ "$PREVIOUS" != "FAIL" ] || [ $(( now - last_notify )) -ge "$RENOTIFY_SECONDS" ]; then
    body=":rotating_light: *EquiMed problem on ${HOSTNAME_S}*"$'\n'
    for f in "${FAILURES[@]}"; do body+=$'\n'"• $f"; done
    body+=$'\n\n'"$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    notify "$body"
    echo "$now" > "$LAST_NOTIFY_FILE"
  fi
elif [ "$PREVIOUS" = "FAIL" ]; then
  notify ":white_check_mark: *EquiMed recovered on ${HOSTNAME_S}* — all checks passing again."
  echo "0" > "$LAST_NOTIFY_FILE"
fi

echo "$CURRENT" > "$STATE_FILE"
[ "$CURRENT" = "OK" ] && exit 0 || exit 1
