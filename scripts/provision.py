#!/usr/bin/env python3
"""Stand up a client's deployment from one config file.

    ./scripts/provision.py clients/acme.yml
    ./scripts/provision.py clients/acme.yml --from 5     # resume after a failure
    ./scripts/provision.py clients/acme.yml --dry-run    # print the plan, do nothing

Replaces docs/fresh-install.md's manual path, including the two steps that used
to need a person in a browser: the ERPNext setup wizard, and generating API
credentials from the desk.

Every step is idempotent. A site build takes ten minutes with a chart of ~1,400
accounts in the middle of it, so partial failures are the normal case and
re-running has to be safe rather than merely tolerated. `--from N` skips ahead
when you already know which step failed.

Secrets are generated here, written to .env with mode 600, and printed once.
They are never read from the config file, so the config can be committed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"

GREEN, YELLOW, RED, DIM, OFF = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def ok(msg):
    print(f"{GREEN}✓{OFF} {msg}")


def warn(msg):
    print(f"{YELLOW}!{OFF} {msg}")


def die(msg):
    print(f"{RED}✗{OFF} {msg}", file=sys.stderr)
    raise SystemExit(1)


def run(cmd, capture=False, check=True, stdin_devnull=True):
    """Run a command in the project root.

    `docker compose exec -T` consumes stdin, so anything not meant to read gets
    /dev/null — otherwise an informational query eats the next prompt's input.
    """
    kwargs = {"cwd": ROOT, "text": True}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.STDOUT
    if stdin_devnull:
        kwargs["stdin"] = subprocess.DEVNULL
    proc = subprocess.run(cmd, **kwargs)
    if check and proc.returncode != 0:
        if capture:
            print(proc.stdout)
        die(f"command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc.stdout if capture else ""


# --------------------------------------------------------------- the config
REQUIRED = {
    "site": ("domain", "erpnext_site"),
    "company": ("name", "abbrev", "country", "timezone", "currency",
                "chart_of_accounts", "fiscal_year_start", "fiscal_year_end"),
    "erpnext_admin": ("email", "full_name"),
    "integration_user": ("email",),
    "app_admin": ("email", "full_name"),
}


def load_config(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        die("PyYAML is needed to read the config: pip3 install pyyaml")

    if not path.is_file():
        die(f"no config at {path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    problems = []
    for section, keys in REQUIRED.items():
        if not isinstance(cfg.get(section), dict):
            problems.append(f"missing section: {section}")
            continue
        for key in keys:
            if not cfg[section].get(key):
                problems.append(f"missing: {section}.{key}")

    # Named separately because it is the one that cannot be undone. ERPNext
    # derives an abbreviation from the company name when none is given, suffixes
    # it onto ~1,400 account names, and the field is set_only_once — so a
    # deployment that guessed it wrong is rebuilt, not corrected.
    abbrev = (cfg.get("company") or {}).get("abbrev")
    if abbrev and not re.fullmatch(r"[A-Za-z0-9]{1,10}", str(abbrev)):
        problems.append(
            f"company.abbrev {abbrev!r} must be 1-10 letters or digits — it is "
            "suffixed onto every account name and cannot be changed later"
        )

    for section in ("erpnext_admin", "integration_user", "app_admin"):
        for key in ("password", "api_key", "api_secret", "secret"):
            if (cfg.get(section) or {}).get(key):
                problems.append(
                    f"{section}.{key} must not be in the config — provisioning "
                    "generates secrets and writes them to .env"
                )

    if problems:
        print(f"{RED}✗{OFF} {path} is not usable:", file=sys.stderr)
        for p in problems:
            print(f"    {p}", file=sys.stderr)
        raise SystemExit(1)
    return cfg


# ------------------------------------------------------------------- .env io
def env_read() -> dict:
    """Parse .env as key/value.

    Never sourced: sourcing *executes* it, so a value like
    `Biomedical Equipment & Supplies` backgrounds a process and tries to run
    "Supplies", and a hostile value would simply run.
    """
    if not ENV.is_file():
        return {}
    out = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.strip()] = value
    return out


def env_write(updates: dict) -> None:
    """Set keys in place, appending any that are new. Everything else is left
    exactly as it was, comments included."""
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.is_file() else []
    remaining = dict(updates)
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        for key in list(remaining):
            if stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}="):
                lines[i] = f"{key}={remaining.pop(key)}"
                break
    if remaining:
        lines.append("")
        lines.append("# Written by scripts/provision.py")
        lines += [f"{k}={v}" for k, v in remaining.items()]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(ENV, 0o600)


def password(n: int = 16) -> str:
    """Readable enough to type off a screen once, long enough not to guess."""
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))


# --------------------------------------------------------------- the steps
def step_1_prerequisites(cfg, state):
    if not shutil.which("docker"):
        die("docker is not installed.")
    version = run(["docker", "compose", "version", "--short"], capture=True).strip()
    major, minor = (version.lstrip("v").split(".") + ["0"])[:2]
    if (int(major), int(re.sub(r"\D", "", minor) or 0)) < (2, 24):
        die(f"docker compose {version} is too old; the production overlay needs "
            "2.24+ for the !override tag, without which the ERPNext desk stays "
            "published to the internet.")
    ok(f"docker compose {version}")


def step_2_env(cfg, state):
    """Write .env, generating any secret that is not already there.

    Existing secrets are never regenerated. Rotating JWT_SECRET_KEY invalidates
    every session, and rotating SECRET_ENCRYPTION_KEY makes stored credentials
    undecryptable — neither belongs in a step people re-run to get past a
    failure.
    """
    if not ENV.is_file():
        shutil.copy(ROOT / ".env.example", ENV)
        ok(".env created from .env.example")

    current = env_read()
    generated = {}

    def keep_or_make(key, maker):
        existing = current.get(key, "")
        if existing and not existing.startswith("CHANGE_ME") and existing not in (
            "admin", "admin12345", "changeme12345"
        ):
            return existing
        value = maker()
        generated[key] = value
        return value

    site = cfg["site"]
    company = cfg["company"]
    updates = {
        "SITE_NAME": site["erpnext_site"],
        "SITE_ADDRESS": site["domain"],
        "CORS_ORIGINS": json.dumps([f"https://{site['domain']}"]),
        "COMPOSE_FILE": "docker-compose.yml:docker-compose.prod.yml",
        "CADDYFILE": "Caddyfile",
        "TENANCY_MODE": "single",
        "DEFAULT_TENANT_NAME": cfg.get("brand", {}).get("name", "EquiMed"),
        "BRAND_APP_NAME": cfg.get("brand", {}).get("name", "EquiMed"),
        "BRAND_SHORT_NAME": cfg.get("brand", {}).get("short_name", ""),
        "BRAND_TAGLINE": cfg.get("brand", {}).get("tagline", ""),
        "DISABLED_ROLES": json.dumps(cfg.get("disabled_roles") or []),
        "FIRST_ADMIN_EMAIL": cfg["app_admin"]["email"],
        "FIRST_ADMIN_NAME": cfg["app_admin"]["full_name"],
        "ALERT_WEBHOOK_URL": cfg.get("alert_webhook_url", ""),
        "ALERT_SITE_URL": f"https://{site['domain']}/api/health",
    }
    for key, length in (("JWT_SECRET_KEY", 32), ("SECRET_ENCRYPTION_KEY", 32),
                        ("PLATFORM_JWT_SECRET_KEY", 32), ("INTERNAL_API_TOKEN", 32),
                        ("BACKUP_ENCRYPTION_KEY", 32)):
        updates[key] = keep_or_make(key, lambda n=length: secrets.token_hex(n))
    for key in ("ADMIN_PASSWORD", "DB_ROOT_PASSWORD", "FIRST_ADMIN_PASSWORD"):
        updates[key] = keep_or_make(key, password)

    env_write(updates)
    state["generated"] = generated
    state["erpnext_admin_password"] = updates["ADMIN_PASSWORD"]
    state["app_admin_password"] = updates["FIRST_ADMIN_PASSWORD"]
    ok(f".env written ({len(generated)} secret(s) generated, mode 600)")
    if company["abbrev"]:
        ok(f"company abbreviation fixed as {company['abbrev']} — set_only_once")


def step_3_stack(cfg, state):
    print(f"{DIM}  building and starting; a first run pulls several GB{OFF}")
    run(["docker", "compose", "up", "-d", "--build"])
    ok("containers up")


def step_4_wait_for_site(cfg, state):
    """The one-shot site creator must finish before anything can talk to it.

    `-a` is load-bearing: `docker compose ps` lists only running containers, so
    a one-shot that already exited vanishes and the wait burns its full timeout
    on a site that was created successfully.
    """
    print(f"{DIM}  waiting for the ERPNext site (first run installs the app){OFF}")
    for _ in range(180):
        line = run(["docker", "compose", "ps", "-a", "--format", "json",
                    "erpnext-create-site"], capture=True, check=False).strip()
        if not line:
            warn("site-creation container not found; continuing")
            return
        first = line.splitlines()[0]
        if '"State":"exited"' in first:
            if '"ExitCode":0' in first:
                ok("ERPNext site created")
            else:
                die("site creation exited non-zero — "
                    "docker compose logs erpnext-create-site")
            return
        time.sleep(10)
    die("timed out waiting for the ERPNext site")


def _bench(script: Path, site: str, payload: Path | None = None) -> str:
    """Run a script inside the ERPNext container.

    Piped as a single line, because `bench console` feeds stdin to IPython,
    which splits multi-line input into cells and dedents function bodies. The
    `globals()` matters too — without it, names bound at module level are
    invisible to functions defined in the same file.
    """
    run(["docker", "compose", "cp", str(script), f"erpnext-backend:/tmp/{script.name}"])
    if payload:
        run(["docker", "compose", "cp", str(payload),
             "erpnext-backend:/tmp/provision.json"])
    one_liner = f'exec(open("/tmp/{script.name}").read(), globals())'
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "erpnext-backend",
         "bench", "--site", site, "console"],
        cwd=ROOT, input=one_liner, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    return proc.stdout


def step_5_bootstrap_erpnext(cfg, state):
    """Setup wizard, taxonomy and API credentials — the browser steps."""
    payload = dict(cfg)
    payload["erpnext_admin"] = dict(cfg["erpnext_admin"])
    payload["erpnext_admin"]["password"] = state.get(
        "erpnext_admin_password", env_read().get("ADMIN_PASSWORD", ""))

    tmp = ROOT / ".provision.json"
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(tmp, 0o600)
    try:
        out = _bench(ROOT / "scripts" / "bootstrap_erpnext.py",
                     cfg["site"]["erpnext_site"], tmp)
    finally:
        tmp.unlink(missing_ok=True)

    for line in out.splitlines():
        if line.strip().startswith("PROVISION_RESULT"):
            result = json.loads(line.split("PROVISION_RESULT", 1)[1])
            break
    else:
        print(out[-3000:])
        die("bootstrap did not report a result — see the output above")

    for w in result.get("warnings", []):
        warn(w)
    env_write({
        "ERPNEXT_API_KEY": result["erpnext_api_key"],
        "ERPNEXT_API_SECRET": result["erpnext_api_secret"],
    })
    state["abbr"] = result.get("abbr")
    ok(f"ERPNext bootstrapped — company {result.get('company')} "
       f"({result.get('abbr')}), API credentials written to .env")


def step_6_company_accounts(cfg, state):
    """The wizard leaves default accounts unset or matched by number prefix —
    on this project's first site the receivable control came out as an
    accrued-interest account — and the company cannot post until they are
    right."""
    out = _bench(ROOT / "scripts" / "configure_company_accounts.py",
                 cfg["site"]["erpnext_site"])
    if "DONE" not in out and "ok" not in out.lower():
        print(out[-2000:])
        warn("company account configuration produced no success marker — check above")
    else:
        ok("company default accounts configured")


def step_7_custom_fields(cfg, state):
    """ERPNext does not reject an unknown field, it drops it. Without these the
    app saves customers with no phone number, and commissioned sales with the
    flag silently gone, and reports nothing wrong."""
    out = _bench(ROOT / "scripts" / "install_custom_fields.py",
                 cfg["site"]["erpnext_site"])
    if "DONE" not in out:
        print(out[-2000:])
        warn("custom fields produced no DONE marker — check above")
    else:
        ok("custom fields installed")


def step_8_backend(cfg, state):
    run(["docker", "compose", "up", "-d", "backend", "frontend"])
    ok("backend restarted with the ERPNext credentials")


def step_9_verify(cfg, state):
    domain = cfg["site"]["domain"]
    for _ in range(30):
        out = run(["docker", "compose", "exec", "-T", "backend",
                   "python", "-c",
                   "import urllib.request;"
                   "print(urllib.request.urlopen('http://localhost:8000/health',"
                   "timeout=5).status)"], capture=True, check=False)
        if "200" in out:
            ok("backend healthy")
            break
        time.sleep(5)
    else:
        warn("backend did not report healthy — docker compose logs backend")

    print()
    print("  Next, by hand:")
    print(f"    - sign in at https://{domain} and set branding under Settings")
    print("    - opening balances via the first-time books setup, if the client")
    print("      is carrying figures over")
    print(f"    - {DIM}scripts/backup-remote.sh --force{OFF} once there is data")


STEPS = [
    ("prerequisites", step_1_prerequisites),
    ("configuration (.env)", step_2_env),
    ("build and start the stack", step_3_stack),
    ("wait for the ERPNext site", step_4_wait_for_site),
    ("ERPNext wizard, taxonomy, API keys", step_5_bootstrap_erpnext),
    ("company default accounts", step_6_company_accounts),
    ("custom fields", step_7_custom_fields),
    ("restart the app", step_8_backend),
    ("verify", step_9_verify),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--from", dest="start", type=int, default=1,
                        help="resume from this step (1-based)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate the config and print the plan")
    args = parser.parse_args()

    cfg = load_config(args.config)
    ok(f"{args.config} is valid")

    print()
    print(f"  {cfg['company']['name']}  ({cfg['company']['abbrev']})")
    print(f"  {cfg['site']['domain']}  ·  {cfg['company']['currency']}"
          f"  ·  {cfg['company']['chart_of_accounts']}")
    print()
    for i, (name, _) in enumerate(STEPS, 1):
        marker = " " if i >= args.start else DIM + "skip" + OFF
        print(f"  {i}. {name}" + (f"   {marker}" if i < args.start else ""))
    print()

    if args.dry_run:
        ok("dry run — nothing was changed")
        return

    state: dict = {}
    for i, (name, fn) in enumerate(STEPS, 1):
        if i < args.start:
            continue
        print(f"{DIM}[{i}/{len(STEPS)}] {name}{OFF}")
        fn(cfg, state)

    print()
    ok("provisioned")
    if state.get("generated"):
        print()
        print(f"{YELLOW}  These are shown once. Put them in a password manager now.{OFF}")
        print(f"    ERPNext Administrator : {state.get('erpnext_admin_password')}")
        print(f"    App admin ({cfg['app_admin']['email']}) : "
              f"{state.get('app_admin_password')}")
        print(f"    Backup encryption key : see BACKUP_ENCRYPTION_KEY in .env")
        print(f"{DIM}    Without the backup key, an off-site backup cannot be "
              f"restored.{OFF}")


if __name__ == "__main__":
    main()
