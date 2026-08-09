"""Audit log behaviour.

The property that matters is not "rows exist" but "rows name the right person".
An audit log that records every action with an empty actor is worse than none:
it looks like accountability and provides none. The first version of this
feature did exactly that — `get_current_user` is a plain `def`, so FastAPI runs
it in a threadpool, and the ContextVar it set was invisible to the middleware
that had to read it. Hence the explicit actor assertions below.
"""

from __future__ import annotations

from middleware.observability import describe
from tests.conftest import auth_header

ADMIN_EMAIL = "admin@equimed.cm"


def _events(client, token, **params):
    resp = client.get("/audit", headers=auth_header(token), params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_a_mutation_is_recorded_with_who_did_it(client, admin_token, fake_erpnext):
    client.post(
        "/customers",
        json={"name": "Audited Clinic", "customer_type": "Company"},
        headers=auth_header(admin_token),
    )
    events = _events(client, admin_token, action="customer.create")
    assert events, "no audit event was written for the mutation"
    e = events[0]
    assert e["actor_email"], "the event has no actor — the log is useless"
    assert e["actor_role"] == "Administrator"
    assert e["actor_id"] is not None
    assert e["resource_type"] == "customer"
    assert e["succeeded"] is True
    assert e["created_at"]
    assert e["request_id"]


def test_a_refused_action_is_recorded_too(client, admin_token, make_token, fake_erpnext):
    """A denial is usually the interesting entry, so failures are kept."""
    sales = make_token("Sales")
    resp = client.post(
        "/users",
        json={"email": "nope@equimed.cm", "full_name": "N", "role": "Sales",
              "password": "whateverpass"},
        headers=auth_header(sales),
    )
    assert resp.status_code == 403

    events = _events(client, admin_token, succeeded=False)
    denied = [e for e in events if e["status_code"] == 403]
    assert denied, "a refused request left no trace"
    assert denied[0]["actor_role"] == "Sales"


def test_reads_are_not_recorded_but_reading_the_audit_log_is(
    client, admin_token, fake_erpnext
):
    """Auditing every GET would bury the signal; auditing audit reads matters."""
    client.get("/customers", headers=auth_header(admin_token))
    assert not [e for e in _events(client, admin_token) if e["action"] == "customer.read"]

    _events(client, admin_token)
    assert [e for e in _events(client, admin_token) if e["action"] == "audit.read"]


def test_the_log_cannot_be_written_or_erased_through_the_api(client, admin_token):
    """Append-only is only real if no route offers the other verbs."""
    for method in ("post", "put", "patch", "delete"):
        resp = getattr(client, method)("/audit", headers=auth_header(admin_token))
        assert resp.status_code in (404, 405), (
            f"{method.upper()} /audit should not exist, got {resp.status_code}"
        )


def test_only_administrators_may_read_it(client, make_token, fake_erpnext):
    for role in ("Manager", "Accountant", "Sales", "Store Keeper",
                 "Biomedical Engineer"):
        resp = client.get("/audit", headers=auth_header(make_token(role)))
        assert resp.status_code == 403, f"{role} could read the audit log"


def test_password_values_never_reach_the_log(client, admin_token, fake_erpnext):
    """Bodies are deliberately not stored; a login would otherwise persist one."""
    secret = "sup3rSecretPassw0rd"
    client.post("/auth/login", data={"username": ADMIN_EMAIL, "password": secret})
    blob = str(_events(client, admin_token, limit=200))
    assert secret not in blob


def test_events_are_newest_first(client, admin_token, fake_erpnext):
    for n in range(3):
        client.post(
            "/customers",
            json={"name": f"Order Test {n}", "customer_type": "Company"},
            headers=auth_header(admin_token),
        )
    events = _events(client, admin_token, action="customer.create", limit=10)
    ids = [e["id"] for e in events]
    assert ids == sorted(ids, reverse=True)


def test_filtering_by_actor(client, admin_token, make_token, fake_erpnext):
    manager = make_token("Manager")
    client.post(
        "/customers",
        json={"name": "Manager Made This", "customer_type": "Company"},
        headers=auth_header(manager),
    )
    all_events = _events(client, admin_token, limit=200)
    mgr = [e for e in all_events if e["actor_role"] == "Manager"]
    assert mgr
    only = _events(client, admin_token, actor_id=mgr[0]["actor_id"], limit=200)
    assert only and all(e["actor_id"] == mgr[0]["actor_id"] for e in only)


# --- action naming -------------------------------------------------------
def test_describe_turns_requests_into_stable_verbs():
    assert describe("POST", "/users") == ("user.create", "user", "")
    assert describe("DELETE", "/users/5") == ("user.delete", "user", "5")
    assert describe("POST", "/auth/login")[0] == "auth.login"
    assert describe("GET", "/audit") == ("audit.read", "audit", "")
    # Document names carry spaces and accents once URL-decoded.
    action, rtype, rid = describe("PUT", "/customers/CHU%20Yaound%C3%A9")
    assert (action, rtype) == ("customer.update", "customer")
    assert rid == "CHU Yaoundé"
    # A sub-resource action reads as its own verb rather than as an id.
    assert describe("POST", "/equipment/SN-1/install")[0] == "equipment.install"


def test_a_successful_login_names_who_signed_in(client, admin_token):
    """Login is unauthenticated, so no dependency identifies the actor.

    Without the route publishing it, every sign-in was recorded against nobody
    — and "who signed in, and when" is the first question asked of an audit log.
    """
    from tests.conftest import ADMIN_PASSWORD, login as do_login

    do_login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    events = _events(client, admin_token, action="auth.login", limit=20)
    ok = [e for e in events if e["succeeded"]]
    assert ok, "no successful login was recorded"
    assert ok[0]["actor_email"] == ADMIN_EMAIL
    assert ok[0]["actor_id"] is not None


def test_a_failed_login_records_the_attempt_without_naming_a_user(
    client, admin_token
):
    """A failed attempt has no authenticated actor, and must not invent one."""
    client.post(
        "/auth/login",
        data={"username": ADMIN_EMAIL, "password": "definitely-wrong"},
    )
    events = _events(client, admin_token, action="auth.login", limit=20)
    failed = [e for e in events if not e["succeeded"]]
    assert failed, "a failed login left no trace"
    assert failed[0]["status_code"] == 401
    assert failed[0]["ip_address"] != ""
