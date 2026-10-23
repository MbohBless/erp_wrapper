#!/usr/bin/env bash
# Ban hosts that repeatedly fail to authenticate over SSH.
#
#   ./scripts/install-fail2ban.sh            # install and configure
#   ./scripts/install-fail2ban.sh --status   # jails, bans, and what is ignored
#   ./scripts/install-fail2ban.sh --unban IP # release one address
#
# WHY ONLY SSH. Port 22 is the one thing on this host genuinely open to the
# internet — 80 and 443 are filtered to Cloudflare in DOCKER-USER, and ERPNext,
# MariaDB and Redis are not published at all. It is also where the volume is:
# ~11,000 failed root passwords a day, enough that /var/log/auth.log reached
# 37 MB. Those arrive as direct connections, so the source address in the
# packet is the attacker's and a firewall rule against it works.
#
# WHY NOT THE WEB PROBES. The /.env and /vendor/composer scanning in Caddy's
# log cannot be banned here, and trying would take the site down. Every request
# reaches this origin through Cloudflare, so the packet source is a Cloudflare
# edge:
#
#   uri=/backend/.git/config  remote_ip=162.159.113.6  client_ip=93.123.109.152
#   uri=/.env                 remote_ip=172.70.46.239  client_ip=45.148.10.67
#
# `remote_ip` is the only thing a firewall can match, and it belongs to
# Cloudflare. Banning it blocks every visitor sharing that edge. The real
# prober is `client_ip`, which exists only inside the log — to act on it you
# have to ban at Cloudflare (IP Access Rules / WAF), not here. Those probes
# are also already answered with 404 by a Next.js app that has no PHP and
# serves nothing from its public directory.
#
# Cloudflare's ranges are in `ignoreip` even though no jail reads a web log
# today. If one is ever added, a careless jail must not be able to ban an edge
# and take the application offline.
set -euo pipefail
cd "$(dirname "$0")/.."

GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; DIM=$'\033[2m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}✓${OFF} $*"; }
warn() { echo "${YELLOW}!${OFF} $*"; }
die()  { echo "${RED}✗${OFF} $*" >&2; exit 1; }

JAIL=/etc/fail2ban/jail.local

# Addresses that must never be banned, whatever the logs say. The two /18 and
# /19 ranges are the Kigali ISPs this deployment is administered from — GVA
# (102.22.128.0/18) and Liquid Telecom Rwanda (41.216.96.0/19). Country-level
# GeoIP files Liquid's range under Mauritius, which is exactly why it is listed
# explicitly rather than inferred.
ADMIN_NETS="${ADMIN_NETS:-102.22.128.0/18 41.216.96.0/19}"

case "${1:-}" in
--status)
    command -v fail2ban-client >/dev/null || die "fail2ban is not installed"
    systemctl is-active --quiet fail2ban && ok "fail2ban running" || warn "fail2ban not running"
    fail2ban-client status 2>/dev/null || true
    echo
    for j in $(fail2ban-client status 2>/dev/null | sed -n 's/.*Jail list:\s*//p' | tr ',' ' '); do
        echo "--- $j ---"; fail2ban-client status "$j" 2>/dev/null
    done
    echo
    echo "ignored:"; fail2ban-client get sshd ignoreip 2>/dev/null | sed 's/^/  /'
    exit 0
    ;;
--unban)
    [ -n "${2:-}" ] || die "usage: $0 --unban <ip>"
    fail2ban-client set sshd unbanip "$2" && ok "unbanned $2"
    exit 0
    ;;
esac

[ "$(id -u)" -eq 0 ] || die "run as root"

# --- install ---------------------------------------------------------------
if ! command -v fail2ban-client >/dev/null; then
    echo "installing fail2ban…"
    DEBIAN_FRONTEND=noninteractive apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq fail2ban >/dev/null
fi
ok "fail2ban $(fail2ban-client --version 2>/dev/null | head -1 | awk '{print $2}')"

# --- Cloudflare ranges, from the same source the DOCKER-USER rules use ------
# Fetched separately and joined with an explicit newline. Running the two
# curls inside one subshell concatenates them, and the v4 list has no trailing
# newline — so its last entry fused with the v6 list's first into
# "131.0.72.0/222400:cb00::/32". fail2ban could not parse that and reduced it
# to a bare 0.0.0.0, which it then matched against every address: the jail
# dutifully ignored every attacker on the internet while reporting itself
# healthy. Two Cloudflare ranges were missing as well.
CF_V4=$(curl -fsS --max-time 20 https://www.cloudflare.com/ips-v4 | tr -d '\r' | grep .) \
   || die "could not fetch Cloudflare's IPv4 ranges — refusing to write a config that omits them"
CF_V6=$(curl -fsS --max-time 20 https://www.cloudflare.com/ips-v6 | tr -d '\r' | grep .) \
   || die "could not fetch Cloudflare's IPv6 ranges — refusing to write a config that omits them"
CF=$(printf '%s\n%s\n' "$CF_V4" "$CF_V6" | grep . | tr '\n' ' ')
[ -n "$CF" ] || die "Cloudflare range list came back empty"

IGNORE="127.0.0.1/8 ::1 $ADMIN_NETS $CF"

# Every entry must be a real address or network. One malformed token does not
# fail loudly in fail2ban — it becomes a wildcard that silently exempts
# everybody, which is the worst possible outcome for a banning tool.
python3 - "$IGNORE" <<'VALIDATE' || die "the ignore list contains an entry that is not an address or network"
import ipaddress, sys
bad = []
for entry in sys.argv[1].split():
    try:
        ipaddress.ip_network(entry, strict=False)
    except ValueError:
        bad.append(entry)
if bad:
    print("  unparseable: %s" % ", ".join(repr(b) for b in bad))
    sys.exit(1)
sys.exit(0)
VALIDATE
ok "ignore list validated ($(echo $IGNORE | wc -w | tr -d ' ') entries, all parseable)"

# --- config ----------------------------------------------------------------
# Written whole each run: a partial edit of someone else's jail.local is how
# a ban action ends up pointing at a chain that no longer exists.
cat > "$JAIL" <<EOF
# Managed by scripts/install-fail2ban.sh — re-run it rather than editing here.
#
# SSH only, deliberately. See the header of that script for why the web probes
# in Caddy's log cannot be banned at this host.

[DEFAULT]
# Never ban: loopback, the Kigali ISPs this host is administered from, and
# every Cloudflare range. The last one is insurance — if a jail reading a web
# log is ever added, it must not be able to ban an edge and take the site down.
ignoreip = $IGNORE

# A repeat offender earns a longer ban each time, to a week. The one-hour
# starting point is enough to break a credential-stuffing run without
# punishing a colleague who mistypes a password twice.
bantime  = 1h
findtime = 10m
maxretry = 4
bantime.increment = true
bantime.factor    = 2
bantime.maxtime   = 1w

# The whole host, not just the port they knocked on — what was asked for, and
# harmless here: 80/443 already refuse everything that is not Cloudflare, and
# nothing else is published.
banaction = iptables-allports

# systemd's journal is the authoritative source on this host; /var/log/auth.log
# is a copy written by rsyslog and could be rotated or disabled independently.
backend = systemd

[sshd]
enabled = true
port    = ssh
# Ubuntu names the unit ssh.service; fail2ban's stock filter looks for
# sshd.service and therefore matches nothing at all. The jail still starts,
# still reports "up", and silently never bans anybody — which is worse than
# not installing it, because the log volume says it is working.
journalmatch = _SYSTEMD_UNIT=ssh.service + _COMM=sshd
EOF
ok "wrote $JAIL"
ok "ignoring $(echo $IGNORE | wc -w | tr -d ' ') networks (loopback, admin, Cloudflare)"

systemctl enable --now fail2ban >/dev/null 2>&1 || true
systemctl restart fail2ban
sleep 3

systemctl is-active --quiet fail2ban || die "fail2ban did not start — journalctl -u fail2ban"
ok "fail2ban active and enabled at boot"

fail2ban-client status sshd >/dev/null 2>&1 || die "the sshd jail did not come up"
ok "sshd jail up"

# "Up" is not "working". The stock filter watches the wrong systemd unit on
# Ubuntu, so a jail can run forever matching nothing. Compare what the journal
# holds against what the jail has actually seen, and fail loudly on a mismatch.
RECENT=$(journalctl -u ssh --since -1h 2>/dev/null | grep -ci "failed password" || true)
sleep 5
SEEN=$(fail2ban-client status sshd 2>/dev/null | sed -n 's/.*Total failed:[^0-9]*\([0-9]*\).*/\1/p' | head -1)
SEEN=${SEEN:-0}
if [ "${RECENT:-0}" -gt 20 ] && [ "$SEEN" -eq 0 ]; then
    die "the journal shows $RECENT failed logins in the last hour but the jail has matched 0 —
   the filter is not reading the right source. Check journalmatch in $JAIL."
fi
ok "filter matching: $SEEN failure(s) seen, $RECENT in the journal this hour"

# The point of the whole exercise: confirm the address this is being run from
# cannot be banned by it.
if [ -n "${SSH_CLIENT:-}" ]; then
    ME="${SSH_CLIENT%% *}"
    if fail2ban-client get sshd ignoreip 2>/dev/null | grep -qF "$ME"; then
        ok "your address $ME is listed explicitly as ignored"
    else
        # Listed by range rather than by address is the normal case.
        python3 - "$ME" "$IGNORE" <<'PY' && ok "your address is inside an ignored range" || warn "your address $ME is NOT in any ignored range — a few bad logins could lock you out"
import ipaddress, sys
ip = ipaddress.ip_address(sys.argv[1])
for net in sys.argv[2].split():
    try:
        if ip in ipaddress.ip_network(net, strict=False):
            sys.exit(0)
    except ValueError:
        pass
sys.exit(1)
PY
    fi
fi

echo
echo "${DIM}  ./scripts/install-fail2ban.sh --status      jails and current bans${OFF}"
echo "${DIM}  ./scripts/install-fail2ban.sh --unban <ip>  release an address${OFF}"
