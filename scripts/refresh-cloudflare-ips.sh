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
  # Rules go in DOCKER-USER, NOT ufw.
  #
  # Docker publishes a port by writing its own netfilter rules, and packets to
  # a container are FORWARDed — they never traverse ufw's INPUT chain. A ufw
  # rule for 80/443 therefore looks correct, reports correct in `ufw status`,
  # and blocks nothing. DOCKER-USER is the chain Docker consults first and the
  # one intended for exactly this.
  command -v iptables >/dev/null || { echo "iptables not available" >&2; exit 1; }
  EXT=$(ip -4 route show default | awk '{print $5}' | head -1)
  [ -n "$EXT" ] || { echo "could not determine the external interface" >&2; exit 1; }
  TAG="equimed-cf"

  echo "  applying DOCKER-USER rules on ${EXT}…"
  # Drop our previous rules (identified by comment) so this is idempotent.
  while n=$(iptables -L DOCKER-USER --line-numbers -n 2>/dev/null | grep -F "$TAG" | head -1 | awk '{print $1}'); [ -n "$n" ]; do
    iptables -D DOCKER-USER "$n"
  done

  # Cloudflare first...
  for cidr in $V4; do
    iptables -A DOCKER-USER -i "$EXT" -s "$cidr" -p tcp -m multiport --dports 80,443 \
      -m comment --comment "$TAG" -j RETURN
  done
  # ...then drop everything else aimed at the published web ports. Anything not
  # matching falls through to DOCKER-USER's implicit RETURN, so container-to-
  # container and outbound traffic are untouched.
  iptables -A DOCKER-USER -i "$EXT" -p tcp -m multiport --dports 80,443 \
    -m comment --comment "$TAG" -j DROP

  echo "  DOCKER-USER now has $(iptables -L DOCKER-USER -n | tail -n +3 | grep -c .) rule(s)"
  echo "  80/443 reachable from Cloudflare only; SSH untouched"
fi
