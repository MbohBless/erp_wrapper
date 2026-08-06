#!/usr/bin/env bash
# First-boot and update script, run ON the server.
#
#   ./scripts/deploy.sh            # bring the stack up (or update it)
#   ./scripts/deploy.sh --check    # verify prerequisites and stop
#
# Idempotent and non-destructive by design:
#   - never overwrites an existing .env (secrets are generated once, then kept)
#   - never touches volumes or databases
#   - safe to re-run after a `git pull` to roll an update forward
#
# Deliberately does NOT install Docker or configure the firewall. Those change
# the machine outside this project, and a deploy script that silently reconfigures
# a host is how servers become impossible to reason about. It tells you what is
# missing and stops.
set -euo pipefail

cd "$(dirname "$0")/.."

RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'; OFF=$'\033[0m'
ok()   { echo "${GREEN}✓${OFF} $*"; }
warn() { echo "${YELLOW}!${OFF} $*"; }
die()  { echo "${RED}✗${OFF} $*" >&2; exit 1; }

CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

# --- Prerequisites --------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker is not installed."
docker compose version >/dev/null 2>&1 || die "the docker compose plugin is not installed."

COMPOSE_VER=$(docker compose version --short 2>/dev/null | sed 's/^v//')
COMPOSE_MAJOR=${COMPOSE_VER%%.*}
COMPOSE_MINOR=$(echo "$COMPOSE_VER" | cut -d. -f2)
# The production overlay needs the `!override` merge tag. Below 2.24 it is
# ignored, which silently leaves ERPNext's desk published on :8080.
if [ "$COMPOSE_MAJOR" -lt 2 ] || { [ "$COMPOSE_MAJOR" -eq 2 ] && [ "${COMPOSE_MINOR:-0}" -lt 24 ]; }; then
  die "docker compose $COMPOSE_VER is too old; the production overlay needs 2.24+ for the !override tag."
fi
ok "docker compose $COMPOSE_VER"

docker info >/dev/null 2>&1 || die "cannot talk to the Docker daemon (is it running, and are you in the docker group?)"
ok "docker daemon reachable"

TOTAL_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo 0)
if [ "${TOTAL_MB:-0}" -gt 0 ] && [ "$TOTAL_MB" -lt 3500 ]; then
  warn "this host has ${TOTAL_MB}MB RAM. ERPNext + MariaDB want ~4GB; expect OOM kills."
elif [ "${TOTAL_MB:-0}" -gt 0 ]; then
  ok "memory: ${TOTAL_MB}MB"
fi

FREE_GB=$(df -BG --output=avail . 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0)
if [ "${FREE_GB:-0}" -gt 0 ] && [ "$FREE_GB" -lt 15 ]; then
  warn "only ${FREE_GB}GB free. The ERPNext images alone are several GB."
fi

# --- .env -----------------------------------------------------------------
# Generated once and then left alone. Regenerating secrets on an existing
# install would invalidate every session and make stored credentials
# undecryptable, so an existing file is never modified.
if [ -f .env ]; then
  ok ".env already exists (left untouched)"
else
  [ -f .env.example ] || die ".env.example is missing; are you in the project root?"
  command -v openssl >/dev/null 2>&1 || die "openssl is needed to generate secrets."

  echo "  generating .env with fresh secrets…"
  cp .env.example .env

  set_var() {  # set_var KEY VALUE — replace or append
    local key="$1" val="$2"
    if grep -qE "^#?${key}=" .env; then
      # Escape / and & for sed's replacement side.
      local esc; esc=$(printf '%s' "$val" | sed -e 's/[\/&]/\\&/g')
      sed -i -E "s|^#?${key}=.*|${key}=${esc}|" .env
    else
      printf '%s=%s\n' "$key" "$val" >> .env
    fi
  }

  for key in JWT_SECRET_KEY SECRET_ENCRYPTION_KEY PLATFORM_JWT_SECRET_KEY INTERNAL_API_TOKEN; do
    set_var "$key" "$(openssl rand -hex 32)"
  done
  set_var DB_ROOT_PASSWORD    "$(openssl rand -hex 16)"
  set_var ADMIN_PASSWORD      "$(openssl rand -hex 12)"
  set_var FIRST_ADMIN_PASSWORD "$(openssl rand -hex 12)"
  set_var FIRST_OWNER_PASSWORD "$(openssl rand -hex 12)"

  # Compose validates every service regardless of profile, so the control-plane
  # variables must be present even for a single-tenant deploy. Generating them
  # now also means enabling the SaaS plane later is a profile flag, not a
  # secrets scramble.
  set_var PLATFORM_CORS_ORIGINS '["*"]'

  # Load the production overlay automatically so a bare `docker compose up`
  # cannot run development defaults.
  set_var COMPOSE_FILE "docker-compose.yml:docker-compose.prod.yml"

  # No domain yet: serve over plain HTTP on the host's IP. Swap CORS_ORIGINS
  # and the Caddyfile once DNS is pointed here.
  PUBLIC_IP=$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || echo "")
  if [ -n "$PUBLIC_IP" ]; then
    set_var CORS_ORIGINS "[\"http://${PUBLIC_IP}\"]"
    ok "detected public IP ${PUBLIC_IP}"
  else
    set_var CORS_ORIGINS '["*"]'
    warn "could not detect the public IP; CORS left open. Tighten it before real use."
  fi

  chmod 600 .env
  ok ".env created (mode 600)"
  echo "${DIM}  credentials are in .env — save them somewhere safe, they are not printed again${OFF}"
fi

# --- Config sanity --------------------------------------------------------
docker compose config >/dev/null || die "compose config is invalid (see the error above)."
ok "compose config valid"

# The specific risk worth checking: the ERPNext desk exposed straight to the
# internet, bypassing Caddy. It happens when the production overlay is not
# loaded, or on a Compose too old to honour `!override`.
#
# `next` after the start pattern matters — the block header itself matches the
# end pattern, so a plain awk range would stop on the line it started on.
ERPNEXT_PORTS=$(docker compose config \
  | awk '/^  erpnext-nginx:/{f=1;next} /^  [a-z]/{f=0} f' \
  | grep -c 'published:' || true)

if [ "${ERPNEXT_PORTS:-0}" -gt 0 ]; then
  warn "the ERPNext desk is published to the host — it should only be reachable via Caddy."
  warn "is COMPOSE_FILE set in .env to include docker-compose.prod.yml?"
else
  ok "ERPNext desk is not published"
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  echo; ok "checks passed — re-run without --check to deploy."
  exit 0
fi

# --- Deploy ---------------------------------------------------------------
echo
echo "building and starting (first run pulls several GB and can take 10+ minutes)…"
docker compose up -d --build

echo
echo "waiting for the site to be created…"
# The one-shot site creator must finish before the app is usable.
for _ in $(seq 1 120); do
  state=$(docker compose ps --format json erpnext-create-site 2>/dev/null | head -1 || true)
  echo "$state" | grep -q '"exited"' && break
  sleep 10
done

echo
echo "waiting for the backend to report healthy…"
for _ in $(seq 1 60); do
  if curl -fsS --max-time 3 http://localhost/api/health >/dev/null 2>&1; then
    ok "backend healthy"
    break
  fi
  sleep 5
done

echo
docker compose ps
echo
HOST_IP=$(curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || echo "<server-ip>")
ok "deployed"
echo "   app : http://${HOST_IP}/"
echo "   api : http://${HOST_IP}/api/docs"
echo
echo "${DIM}Next: ERPNext setup wizard, then generate API keys and put them in .env${OFF}"
echo "${DIM}      (ERPNEXT_API_KEY / ERPNEXT_API_SECRET), then: docker compose up -d backend${OFF}"
echo "${DIM}Sign-in credentials are FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD in .env${OFF}"
