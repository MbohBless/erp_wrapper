#!/usr/bin/env bash
# Refresh Cloudflare's published IP ranges in two places that must agree:
#
#   caddy/Caddyfile   trusted_proxies — which peers may set CF-Connecting-IP
#   ufw               who may reach ports 80/443 at all
#
# Cloudflare changes these rarely, but when they do, a stale list means either
# real visitor IPs stop resolving (Caddy) or legitimate traffic is dropped
# (ufw). Run this, then restart Caddy.
#
#   ./scripts/refresh-cloudflare-ips.sh            # update the Caddyfile
#   ./scripts/refresh-cloudflare-ips.sh --firewall # also rewrite ufw rules
#
# --firewall is destructive to existing 80/443 rules and is deliberately opt-in.
# SSH is never touched.
set -euo pipefail
cd "$(dirname "$0")/.."

V4=$(curl -fsS --max-time 20 https://www.cloudflare.com/ips-v4 | tr -d '\r' | grep .)
V6=$(curl -fsS --max-time 20 https://www.cloudflare.com/ips-v6 | tr -d '\r' | grep .)
[ -n "$V4" ] || { echo "could not fetch Cloudflare IPv4 ranges" >&2; exit 1; }
ALL=$(printf '%s\n%s\n' "$V4" "$V6" | paste -sd' ' -)

python3 - "$ALL" <<'PY'
import pathlib, re, sys
ranges = sys.argv[1]
p = pathlib.Path("caddy/Caddyfile"); s = p.read_text()
new, n = re.subn(r"(\t\ttrusted_proxies static ).*", r"\g<1>" + ranges, s, count=1)
if not n:
    print("  trusted_proxies line not found — Caddyfile changed shape?"); raise SystemExit(1)
p.write_text(new)
print(f"  Caddyfile updated ({len(ranges.split())} ranges)")
PY

if [ "${1:-}" = "--firewall" ]; then
  command -v ufw >/dev/null || { echo "ufw not installed" >&2; exit 1; }
  echo "  rewriting ufw rules for 80/443…"
  # Drop existing 80/443 rules (highest number first so indices stay valid).
  ufw status numbered | grep -E '(^\[.*\] )(80|443)/tcp' | grep -oE '^\[[ 0-9]+\]' \
    | tr -d '[] ' | sort -rn | while read -r n; do yes | ufw delete "$n" >/dev/null; done
  for cidr in $ALL; do
    ufw allow proto tcp from "$cidr" to any port 80,443 >/dev/null
  done
  echo "  ufw now allows 80/443 from Cloudflare only (SSH untouched)"
  ufw status | head -3
fi
