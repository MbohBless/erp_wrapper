#!/usr/bin/env bash
# Install the health watchdog as a systemd timer.
#
#   sudo ./scripts/install-watchdog.sh
#
# A systemd timer rather than cron, for two reasons that matter here: it starts
# after Docker (so a reboot does not fire a checker that reports everything down
# while the stack is still coming up), and `systemctl status` shows the last run
# and its output without going log-hunting.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO="$(pwd)"

GREEN=$'\033[32m'; YELLOW=$'\033[33m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}✓${OFF} $*"; }
warn() { echo "${YELLOW}!${OFF} $*"; }

[ "$(id -u)" -eq 0 ] || { echo "run as root (systemd units + /var/lib)"; exit 1; }

if ! grep -q '^ALERT_WEBHOOK_URL=' .env 2>/dev/null; then
  warn "ALERT_WEBHOOK_URL is not set in .env — the watchdog will run but stay silent."
  warn "Add a Slack or Discord incoming-webhook URL, then re-run with --test."
fi

cat > /etc/systemd/system/equimed-watchdog.service <<EOF
[Unit]
Description=EquiMed health watchdog
# Do not check the stack before the stack exists: after a reboot this would
# otherwise fire a full outage alert while Docker is still starting.
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${REPO}
ExecStart=${REPO}/scripts/watchdog.sh
# A failing check is the normal case for this unit, not a unit failure.
SuccessExitStatus=0 1
EOF

cat > /etc/systemd/system/equimed-watchdog.timer <<'EOF'
[Unit]
Description=Run the EquiMed health watchdog every 5 minutes

[Timer]
# Wait for the stack to settle after a boot before the first check.
OnBootSec=3min
OnUnitActiveSec=5min
# Stagger slightly so every host does not check on the same second.
RandomizedDelaySec=30
Persistent=true

[Install]
WantedBy=timers.target
EOF

mkdir -p /var/lib/equimed-watchdog
chmod +x "${REPO}/scripts/watchdog.sh"

systemctl daemon-reload
systemctl enable --now equimed-watchdog.timer
ok "watchdog timer installed and enabled (every 5 minutes)"
echo
systemctl list-timers equimed-watchdog.timer --no-pager | head -3
echo
echo "Next:"
echo "  ./scripts/watchdog.sh --status   # what it sees right now"
echo "  ./scripts/watchdog.sh --test     # prove the webhook works"
