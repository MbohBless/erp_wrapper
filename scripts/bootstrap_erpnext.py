"""Bring a fresh ERPNext site to a usable state, from a config file.

Runs INSIDE the erpnext-backend container. `scripts/provision.py` copies this
and the config next to it and invokes it; it is not meant to be run by hand,
though it is safe to:

    docker compose cp scripts/bootstrap_erpnext.py erpnext-backend:/tmp/bs.py
    docker compose cp /tmp/provision.json erpnext-backend:/tmp/provision.json
    echo 'exec(open("/tmp/bs.py").read(), globals())' \\
      | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console

Replaces the three steps of docs/fresh-install.md that used to need a person in
a browser: the setup wizard, the taxonomy, and generating API credentials.

Every step is idempotent. A site build takes ten minutes and partial failures
are the normal case, so re-running has to be safe rather than merely tolerated.

Results the caller needs — chiefly the API secret, which ERPNext returns exactly
once — are printed on a single line prefixed with PROVISION_RESULT, because
bench console's output is otherwise not machine-readable.
"""

import json

import frappe

CONFIG_PATH = "/tmp/provision.json"
RESULT_MARKER = "PROVISION_RESULT"

_result = {"steps": [], "warnings": []}


def step(name, detail=""):
    print("  %-34s %s" % (name, detail))
    _result["steps"].append({"step": name, "detail": detail})


def warn(message):
    print("  !  %s" % message)
    _result["warnings"].append(message)


# ---------------------------------------------------------------- the wizard
def run_setup_wizard(cfg):
    """Complete the setup wizard from config instead of a browser.

    The abbreviation is the reason this is worth automating rather than
    documenting. ERPNext derives it from the company name and it is
    `set_only_once` — suffixed onto ~1,400 account names, and the only way to
    change it afterwards is to rebuild the site. Typed into a wizard it is a
    field people tab past; here it is a reviewed line in a file.
    """
    if frappe.db.get_single_value("System Settings", "setup_complete"):
        company = frappe.db.get_value(
            "Company", cfg["company"]["name"], ["name", "abbr"], as_dict=True
        )
        if company and company.abbr != cfg["company"]["abbrev"]:
            warn(
                "site already set up as %r with abbreviation %r, but the config "
                "asks for %r. The abbreviation is set_only_once — this site "
                "cannot be changed to match; rebuild it or change the config."
                % (company.name, company.abbr, cfg["company"]["abbrev"])
            )
        step("setup wizard", "already complete — skipped")
        return

    c = cfg["company"]
    args = {
        "language": cfg.get("language", "English"),
        "country": c["country"],
        "timezone": c["timezone"],
        "currency": c["currency"],
        "company_name": c["name"],
        "company_abbr": c["abbrev"],
        "chart_of_accounts": c["chart_of_accounts"],
        "fy_start_date": c["fiscal_year_start"],
        "fy_end_date": c["fiscal_year_end"],
        "company_tagline": cfg.get("brand", {}).get("tagline", ""),
        "full_name": cfg["erpnext_admin"]["full_name"],
        "email": cfg["erpnext_admin"]["email"],
        "password": cfg["erpnext_admin"]["password"],
        "setup_demo": 0,
    }
    from erpnext.setup.setup_wizard.setup_wizard import setup_complete

    try:
        setup_complete(args)
    except Exception as exc:
        # The payload keys move between ERPNext versions, so show what was sent
        # rather than leaving someone to guess which one it disliked.
        print("  setup_complete failed with: %r" % (exc,))
        print("  payload was: %s" % json.dumps(
            {k: ("***" if k == "password" else v) for k, v in args.items()}, indent=2))
        raise
    frappe.db.commit()
    step("setup wizard", "%s (%s), %s, %s" % (
        c["name"], c["abbrev"], c["currency"], c["chart_of_accounts"]))


# -------------------------------------------------------------- the taxonomy
def _ensure_leaves(doctype, root, name_field, wanted):
    """Create each wanted value as a *leaf* under the tree root.

    Leaves, because ERPNext refuses a group node on a transaction. A value
    created as a group looks selectable in every picker and fails at save.
    """
    created, fixed = [], []
    for name in wanted:
        if frappe.db.exists(doctype, name):
            if frappe.db.get_value(doctype, name, "is_group"):
                frappe.db.set_value(doctype, name, "is_group", 0)
                fixed.append(name)
            continue
        doc = frappe.get_doc({
            "doctype": doctype,
            name_field: name,
            "parent_" + frappe.scrub(doctype): root,
            "is_group": 0,
        })
        doc.insert(ignore_permissions=True)
        created.append(name)
    frappe.db.commit()
    detail = "%d present" % len(wanted)
    if created:
        detail += ", created %s" % ", ".join(created)
    if fixed:
        detail += ", made selectable %s" % ", ".join(fixed)
    return detail


def configure_taxonomy(cfg):
    tax = cfg.get("taxonomy") or {}
    if tax.get("customer_groups"):
        step("customer groups", _ensure_leaves(
            "Customer Group", "All Customer Groups", "customer_group_name",
            tax["customer_groups"]))
    if tax.get("item_groups"):
        step("item categories", _ensure_leaves(
            "Item Group", "All Item Groups", "item_group_name",
            tax["item_groups"]))
    if tax.get("territories"):
        step("territories", _ensure_leaves(
            "Territory", "All Territories", "territory_name", tax["territories"]))


# ------------------------------------------------- the integration account
def ensure_integration_user(cfg):
    """A service account for the app, and its API credentials.

    Not Administrator, and emphatically not a person: whoever owns this key owns
    every document the app creates in ERPNext's audit trail, and disabling that
    human — or trimming their roles — stops the integration dead. A named
    service account also makes rotation a routine act rather than one that
    touches someone's login.

    The secret is returned by ERPNext exactly once, at generation. It is
    captured here and handed back to the caller; there is no reading it later,
    only replacing it.
    """
    account = cfg["integration_user"]
    email = account["email"]

    if not frappe.db.exists("User", email):
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": account.get("full_name", "Integration"),
            "send_welcome_email": 0,
            "user_type": "System User",
        })
        user.insert(ignore_permissions=True)
        created = True
    else:
        user = frappe.get_doc("User", email)
        created = False

    wanted_roles = account.get("roles") or ["System Manager"]
    existing = {r.role for r in user.roles}
    for role in wanted_roles:
        if role not in existing:
            user.append("roles", {"role": role})
    user.enabled = 1
    user.save(ignore_permissions=True)
    frappe.db.commit()

    from frappe.core.doctype.user.user import generate_keys

    # Regenerates on every run by design. The secret cannot be read back, so a
    # provisioning run that did not produce one would leave the caller with
    # nothing to write into .env — and a key nobody holds is worse than a new one.
    api_secret = generate_keys(email)
    if isinstance(api_secret, dict):
        api_secret = api_secret.get("api_secret")
    frappe.db.commit()

    api_key = frappe.db.get_value("User", email, "api_key")
    step("integration user", "%s (%s), roles: %s" % (
        email, "created" if created else "existing", ", ".join(wanted_roles)))
    _result["erpnext_api_key"] = api_key
    _result["erpnext_api_secret"] = api_secret


# --------------------------------------------------------------------- main
def main():
    cfg = json.load(open(CONFIG_PATH))
    print("--- bootstrapping %s ---" % cfg["company"]["name"])
    run_setup_wizard(cfg)
    configure_taxonomy(cfg)
    ensure_integration_user(cfg)

    _result["ok"] = True
    _result["company"] = cfg["company"]["name"]
    _result["abbr"] = frappe.db.get_value("Company", cfg["company"]["name"], "abbr")
    print()
    print("%s %s" % (RESULT_MARKER, json.dumps(_result)))


main()
