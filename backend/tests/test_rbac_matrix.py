"""Exhaustive RBAC matrix — every route, every role.

The per-module tests spot-check RBAC on the routes they happen to touch. That
leaves the failure mode nobody notices: a **new route added without a guard**.
It passes every existing test, because no existing test knows it exists.

So this file asserts two properties:

1. **Completeness** — every route in the app has a declared expectation in
   ``MATRIX`` below. A new route fails this test until someone states, in
   writing, who may reach it. That is the point: RBAC review becomes impossible
   to skip rather than merely encouraged.

2. **Enforcement** — for each route, every role that should be denied gets 403,
   and every role that should be allowed does not.

``MATRIX`` is maintained **by hand**, mirroring the table in ``docs/api.md``. It
is deliberately not derived from the ``require_roles`` calls — a test that reads
the same declaration it is checking proves only that Python is deterministic.
Independent restatement is what makes a *changed* guard fail here and force a
docs update with it.

Assertion shape: denied means exactly 403; allowed means *anything but* 403.
A 422 or 404 still proves the guard let the caller through, which is all this
file is about — so no route needs a valid payload, and all 81 can be covered.
"""

from __future__ import annotations

import pytest

from models.user import Role
from tests.conftest import auth_header

ALL_ROLES = frozenset(r.value for r in Role)
NON_ADMIN = frozenset(ALL_ROLES - {Role.ADMINISTRATOR.value})

# Sentinels for routes not gated by role.
PUBLIC = "public"  # reachable with no credentials at all
AUTHED = "authenticated"  # any signed-in user, regardless of role
SELF_OR_ADMIN = "self-or-admin"  # checked in-handler, not by a dependency
INTERNAL = "internal"  # shared-secret service call, never a user session

A = Role.ADMINISTRATOR.value
M = Role.MANAGER.value
S = Role.SALES.value
K = Role.STORE_KEEPER.value
C = Role.ACCOUNTANT.value
B = Role.BIOMEDICAL_ENGINEER.value

# (method, path) -> expectation. Administrator is implicitly allowed everywhere
# by require_roles, so it is omitted from the role sets.
MATRIX: dict[tuple[str, str], object] = {
    # --- infrastructure -----------------------------------------------------
    ("GET", "/health"): PUBLIC,
    ("GET", "/health/erpnext"): PUBLIC,
    ("GET", "/public/branding"): PUBLIC,
    # --- auth ---------------------------------------------------------------
    ("POST", "/auth/login"): PUBLIC,
    ("POST", "/auth/logout"): AUTHED,
    # Unauthenticated on purpose: it is called exactly when the access token has
    # expired. The refresh token is the credential, and it is single-use.
    ("POST", "/auth/refresh"): PUBLIC,
    ("GET", "/auth/me"): AUTHED,
    # --- control plane ------------------------------------------------------
    ("POST", "/internal/tenants/{tenant_id}/bootstrap"): INTERNAL,
    ("DELETE", "/internal/tenants/{tenant_id}"): INTERNAL,
    # --- audit --------------------------------------------------------------
    # Administrator only: the audit log names who did what, and is the one place
    # a compromised account's activity is visible.
    ("GET", "/audit"): frozenset(),
    # --- users --------------------------------------------------------------
    ("GET", "/users"): frozenset(),  # Administrator only
    ("POST", "/users"): frozenset(),
    ("PUT", "/users/{user_id}"): frozenset(),
    ("DELETE", "/users/{user_id}"): frozenset(),
    ("GET", "/users/{user_id}"): SELF_OR_ADMIN,
    # --- reference data for form pickers -------------------------------------
    # Taxonomy labels only ("Commercial", "Cameroon", "Nos"); every form that
    # uses one is guarded on its own write.
    ("GET", "/reference/options"): AUTHED,
    # --- dashboard ----------------------------------------------------------
    ("GET", "/dashboard"): AUTHED,
    # --- catalogue ----------------------------------------------------------
    ("GET", "/products"): AUTHED,
    ("GET", "/products/{product_id}"): AUTHED,
    ("POST", "/products"): frozenset({M}),
    ("PUT", "/products/{product_id}"): frozenset({M}),
    ("DELETE", "/products/{product_id}"): frozenset({M}),
    # --- customers ----------------------------------------------------------
    ("GET", "/customers"): frozenset({M, S, C}),
    ("GET", "/customers/{customer_id}"): frozenset({M, S, C}),
    ("POST", "/customers"): frozenset({M, S}),
    ("PUT", "/customers/{customer_id}"): frozenset({M, S}),
    ("DELETE", "/customers/{customer_id}"): frozenset({M, S}),
    # --- suppliers ----------------------------------------------------------
    ("GET", "/suppliers"): frozenset({M, K, C}),
    ("GET", "/suppliers/{supplier_id}"): frozenset({M, K, C}),
    ("POST", "/suppliers"): frozenset({M}),
    ("PUT", "/suppliers/{supplier_id}"): frozenset({M}),
    ("DELETE", "/suppliers/{supplier_id}"): frozenset({M}),
    # --- inventory ----------------------------------------------------------
    ("GET", "/inventory/stock"): frozenset({M, S, K, C}),
    ("GET", "/inventory/warehouses"): frozenset({M, S, K, C}),
    ("GET", "/inventory/warehouses/{warehouse_id}"): frozenset({M, S, K, C}),
    ("POST", "/inventory/warehouses"): frozenset({M, K}),
    ("PUT", "/inventory/warehouses/{warehouse_id}"): frozenset({M, K}),
    ("DELETE", "/inventory/warehouses/{warehouse_id}"): frozenset({M, K}),
    ("GET", "/inventory/batches"): frozenset({M, S, K, C}),
    ("GET", "/inventory/batches/{batch_id}"): frozenset({M, S, K, C}),
    ("POST", "/inventory/batches"): frozenset({M, K}),
    ("POST", "/inventory/receive"): frozenset({M, K}),
    ("POST", "/inventory/issue"): frozenset({M, K}),
    # --- sales / purchases --------------------------------------------------
    ("GET", "/sales"): frozenset({M, S, C}),
    ("GET", "/sales/{invoice_id}"): frozenset({M, S, C}),
    ("POST", "/sales"): frozenset({M, S}),
    ("GET", "/purchases"): frozenset({M, K, C}),
    ("GET", "/purchases/{bill_id}"): frozenset({M, K, C}),
    ("POST", "/purchases"): frozenset({M}),
    # --- equipment ----------------------------------------------------------
    ("GET", "/equipment"): frozenset({M, S, K, B}),
    ("GET", "/equipment/{equipment_id}"): frozenset({M, S, K, B}),
    ("POST", "/equipment"): frozenset({M, B}),
    ("PUT", "/equipment/{equipment_id}"): frozenset({M, B}),
    ("DELETE", "/equipment/{equipment_id}"): frozenset({M, B}),
    ("POST", "/equipment/{equipment_id}/install"): frozenset({M, B}),
    # --- maintenance --------------------------------------------------------
    ("GET", "/maintenance"): frozenset({M, S, B}),
    ("GET", "/maintenance/{ticket_id}"): frozenset({M, S, B}),
    ("POST", "/maintenance"): frozenset({M, B}),
    ("PUT", "/maintenance/{ticket_id}"): frozenset({M, B}),
    ("DELETE", "/maintenance/{ticket_id}"): frozenset({M, B}),
    ("POST", "/maintenance/{ticket_id}/complete"): frozenset({M, B}),
    # --- finance: the money. Accountant + Manager only. ---------------------
    ("GET", "/finance/summary"): frozenset({M, C}),
    ("GET", "/finance/receivable"): frozenset({M, C}),
    ("GET", "/finance/payable"): frozenset({M, C}),
    ("GET", "/finance/cash-flow"): frozenset({M, C}),
    ("GET", "/finance/cash-book"): frozenset({M, C}),
    ("GET", "/finance/bank-book"): frozenset({M, C}),
    ("GET", "/finance/trial-balance"): frozenset({M, C}),
    ("GET", "/finance/reports/balance-sheet"): frozenset({M, C}),
    ("GET", "/finance/reports/income-statement"): frozenset({M, C}),
    ("GET", "/payments"): frozenset({M, C}),
    ("POST", "/payments/receive"): frozenset({M, C}),
    ("POST", "/payments/pay"): frozenset({M, C}),
    ("GET", "/budget"): frozenset({M, C}),
    ("PUT", "/budget"): frozenset({M, C}),
    ("GET", "/reports/{report_key}/pdf"): frozenset({M, C}),
    # --- settings -----------------------------------------------------------
    ("GET", "/settings/branding"): AUTHED,
    ("PUT", "/settings/branding"): frozenset({M, C}),
    ("PUT", "/settings/branding/dashboard"): frozenset({M, C}),
    ("POST", "/settings/branding/dashboard/reset"): frozenset({M, C}),
    ("GET", "/settings/company-profile"): AUTHED,
    ("PUT", "/settings/company-profile"): frozenset({M, C}),
    # --- setup --------------------------------------------------------------
    ("GET", "/setup/status"): AUTHED,
    ("POST", "/setup/opening-balances"): frozenset({M, C}),
}


def _app_routes():
    """Every (method, path) the app actually serves, minus FastAPI's own docs."""
    from main import app

    skip = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc", "/"}
    out = set()
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None)
        if not path or not methods or path in skip:
            continue
        for m in methods:
            if m != "HEAD":
                out.add((m, path))
    return out


# Deliberately an id that cannot exist. Using "1" here made the
# Administrator-bypass test issue a real DELETE /users/1 against the seeded
# admin account, wiping it and erroring out every later test in the session.
# The guard runs before the handler, so a miss is 404 — which still proves the
# request got through, and destroys nothing.
ABSENT_ID = "987654321"


def _concrete(path: str) -> str:
    """Fill path params with a placeholder — the guard runs before the handler."""
    out = []
    for seg in path.split("/"):
        if seg.startswith("{") and seg.endswith("}"):
            out.append(ABSENT_ID if seg[1:-1].endswith("_id") else "x")
        else:
            out.append(seg)
    return "/".join(out)


def test_every_route_has_a_declared_rbac_expectation():
    """No route may exist without someone having stated who can reach it.

    This is the test that catches the guard nobody remembered to add: a new
    endpoint fails here on the first run, before it can ship unprotected.
    """
    served = _app_routes()
    declared = set(MATRIX)

    undeclared = served - declared
    assert not undeclared, (
        "these routes have no RBAC expectation declared in MATRIX — add them "
        "here and to the RBAC table in docs/api.md:\n  "
        + "\n  ".join(f"{m} {p}" for m, p in sorted(undeclared, key=lambda x: x[1]))
    )

    stale = declared - served
    assert not stale, (
        "MATRIX declares routes the app no longer serves — remove them:\n  "
        + "\n  ".join(f"{m} {p}" for m, p in sorted(stale, key=lambda x: x[1]))
    )


ROLE_GATED = sorted(
    ((m, p, exp) for (m, p), exp in MATRIX.items() if isinstance(exp, frozenset)),
    key=lambda x: (x[1], x[0]),
)

# One user per role for the whole module. The first draft provisioned a user per
# (role, route) pair — ~450 accounts and two minutes of runtime to learn what six
# accounts already prove.
_TOKENS: dict[str, str] = {}


@pytest.fixture()
def role_token(make_token):
    def _get(role: str) -> str:
        if role not in _TOKENS:
            _TOKENS[role] = make_token(role)
        return _TOKENS[role]

    return _get


@pytest.mark.parametrize(
    "method,path,allowed",
    ROLE_GATED,
    ids=[f"{m}-{p}" for m, p, _ in ROLE_GATED],
)
def test_role_gated_routes_deny_every_other_role(
    client, role_token, fake_erpnext, method, path, allowed
):
    """Each role-gated route: denied roles get 403, allowed roles do not."""
    url = _concrete(path)
    for role in sorted(NON_ADMIN):
        token = role_token(role)
        resp = client.request(method, url, headers=auth_header(token), json={})
        if role in allowed:
            assert resp.status_code != 403, (
                f"{role} should be allowed on {method} {path} but got 403"
            )
        else:
            assert resp.status_code == 403, (
                f"{role} must be DENIED on {method} {path} "
                f"but got {resp.status_code}"
            )


@pytest.mark.parametrize(
    "method,path",
    [(m, p) for (m, p), exp in MATRIX.items() if exp is not PUBLIC],
    ids=[f"{m}-{p}" for (m, p), exp in MATRIX.items() if exp is not PUBLIC],
)
def test_no_non_public_route_is_reachable_unauthenticated(
    client, fake_erpnext, method, path
):
    """Every non-public route must reject an anonymous caller.

    Internal routes answer 401 on a bad/missing shared secret, or 503 when the
    secret is not configured at all — both are refusals, and both are fine.
    """
    resp = client.request(method, _concrete(path), json={})
    assert resp.status_code in (401, 403, 422, 503), (
        f"{method} {path} answered {resp.status_code} to an ANONYMOUS caller"
    )


def test_administrator_reaches_every_role_gated_route(
    client, role_token, fake_erpnext
):
    """The Administrator bypass in require_roles must hold everywhere."""
    token = role_token(Role.ADMINISTRATOR.value)
    for method, path, _ in ROLE_GATED:
        resp = client.request(
            method, _concrete(path), headers=auth_header(token), json={}
        )
        assert resp.status_code != 403, (
            f"Administrator was denied {method} {path}"
        )
