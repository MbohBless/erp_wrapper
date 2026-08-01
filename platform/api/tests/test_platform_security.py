"""Control-plane RBAC, internal-API auth, secret handling and domain safety.

The control plane can suspend every customer at once, so its own access control
matters more than any single tenant's.
"""

from tests.conftest import auth_header, internal_header, login


# --- Operator RBAC --------------------------------------------------------
def test_support_operator_can_read_but_not_mutate(client, make_operator, new_tenant):
    new_tenant("readonly-target")
    token = make_operator("Support")["token"]

    assert client.get("/tenants", headers=auth_header(token)).status_code == 200

    blocked = client.post(
        "/tenants",
        json={
            "id": "support-made-this",
            "name": "Nope",
            "plan_code": "starter",
            "admin_email": "a@nope.example",
            "admin_password": "workspacepass123",
        },
        headers=auth_header(token),
    )
    assert blocked.status_code == 403

    suspend = client.post(
        "/tenants/readonly-target/suspend",
        json={"reason": "should not work"},
        headers=auth_header(token),
    )
    assert suspend.status_code == 403


def test_operator_can_suspend_but_not_purge(client, make_operator, new_tenant, owner_token):
    made = new_tenant("operator-scope")
    token = make_operator("Operator")["token"]

    assert (
        client.post(
            "/tenants/operator-scope/suspend",
            json={"reason": "ok"},
            headers=auth_header(token),
        ).status_code
        == 200
    )
    client.post("/tenants/operator-scope/archive", headers=auth_header(token)).raise_for_status()

    purge = client.delete(
        "/tenants/operator-scope",
        params={"confirm": "operator-scope"},
        headers=auth_header(token),
    )
    assert purge.status_code == 403, "purge is owner-only"


def test_billing_operator_manages_plans_but_not_tenants(client, make_operator):
    token = make_operator("Billing")["token"]
    assert client.get("/plans", headers=auth_header(token)).status_code == 200
    created = client.post(
        "/plans",
        json={"code": "trial", "name": "Trial", "features": ["reports"], "max_users": 2},
        headers=auth_header(token),
    )
    assert created.status_code == 201

    blocked = client.post(
        "/tenants",
        json={
            "id": "billing-made-this",
            "name": "Nope",
            "plan_code": "trial",
            "admin_email": "a@nope.example",
            "admin_password": "workspacepass123",
        },
        headers=auth_header(token),
    )
    assert blocked.status_code == 403


def test_only_owners_manage_operators(client, make_operator):
    token = make_operator("Operator")["token"]
    assert client.get("/operators", headers=auth_header(token)).status_code == 403


def test_disabled_operator_cannot_authenticate(client, owner_token, make_operator):
    operator = make_operator("Support")
    assert login(client, operator["email"], operator["password"]).status_code == 200

    client.patch(
        f"/operators/{operator['id']}",
        json={"is_active": False},
        headers=auth_header(owner_token),
    ).raise_for_status()

    resp = login(client, operator["email"], operator["password"])
    assert resp.status_code == 403


def test_a_disabled_operators_existing_token_stops_working(
    client, owner_token, make_operator
):
    """Disabling must revoke in-flight sessions, not just block new logins."""
    operator = make_operator("Operator")
    assert client.get("/tenants", headers=auth_header(operator["token"])).status_code == 200

    client.patch(
        f"/operators/{operator['id']}",
        json={"is_active": False},
        headers=auth_header(owner_token),
    ).raise_for_status()

    assert client.get("/tenants", headers=auth_header(operator["token"])).status_code == 403


def test_last_active_owner_cannot_be_disabled(client, owner_token):
    operators = client.get("/operators", headers=auth_header(owner_token)).json()
    owner = next(o for o in operators if o["role"] == "Owner" and o["is_active"])
    resp = client.patch(
        f"/operators/{owner['id']}",
        json={"is_active": False},
        headers=auth_header(owner_token),
    )
    assert resp.status_code == 409
    assert "last active owner" in resp.json()["detail"].lower()


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/tenants").status_code == 401
    assert client.get("/plans").status_code == 401
    assert client.get("/audit").status_code == 401


# --- Internal API ---------------------------------------------------------
def test_resolve_requires_the_shared_secret(client, new_tenant):
    new_tenant("secretive")
    assert (
        client.get(
            "/internal/tenants/resolve", params={"host": "secretive.equimed.test"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/internal/tenants/resolve",
            params={"host": "secretive.equimed.test"},
            headers={"X-Internal-Token": "wrong-token"},
        ).status_code
        == 401
    )


def test_resolve_returns_plan_features(client, new_tenant, owner_token):
    made = new_tenant("featured", plan="business")
    client.post(
        "/tenants/featured/provision", json=made["payload"], headers=auth_header(owner_token)
    ).raise_for_status()

    resp = client.get(
        "/internal/tenants/resolve",
        params={"host": "featured.equimed.test"},
        headers=internal_header(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "business"
    assert "branding" in body["features"]
    # Business does not include custom dashboards.
    assert "dashboard_layout" not in body["features"]


def test_resolve_404s_for_an_unknown_host(client):
    resp = client.get(
        "/internal/tenants/resolve",
        params={"host": "nobody.equimed.test"},
        headers=internal_header(),
    )
    assert resp.status_code == 404


# --- Secret handling ------------------------------------------------------
def test_erpnext_secret_is_encrypted_at_rest_and_never_returned(
    client, owner_token, new_tenant
):
    new_tenant("vaulted", erpnext_api_key="key-live", erpnext_api_secret="super-secret-value")

    # The admin API acknowledges a secret exists but never echoes it.
    read = client.get("/tenants/vaulted", headers=auth_header(owner_token)).json()
    assert read["has_erpnext_secret"] is True
    assert "super-secret-value" not in str(read)

    # It is stored as ciphertext...
    from database import SessionLocal
    from models.tenant import Tenant

    db = SessionLocal()
    try:
        stored = db.get(Tenant, "vaulted").erpnext_api_secret_enc
    finally:
        db.close()
    assert stored.startswith("enc:v1:")
    assert "super-secret-value" not in stored

    # ...and only the internal resolve endpoint decrypts it.
    resolved = client.get(
        "/internal/tenants/resolve",
        params={"host": "vaulted.equimed.test"},
        headers=internal_header(),
    ).json()
    assert resolved["erpnext_api_secret"] == "super-secret-value"


def test_crypto_roundtrip_and_wrong_key_behaviour():
    from utils.crypto import decrypt, encrypt

    token = encrypt("hello")
    assert token != "hello"
    assert decrypt(token) == "hello"
    # Legacy plaintext passes through rather than raising.
    assert decrypt("plain-value") == "plain-value"
    assert encrypt("") == "" and decrypt("") == ""


# --- Domains / TLS --------------------------------------------------------
def test_custom_domain_requires_the_plan_feature(client, owner_token, new_tenant):
    new_tenant("basicco", plan="starter")
    resp = client.post(
        "/tenants/basicco/domains",
        json={"host": "erp.basicco.cm"},
        headers=auth_header(owner_token),
    )
    assert resp.status_code == 402


def test_custom_domain_lifecycle_and_tls_gate(client, owner_token, new_tenant):
    new_tenant("bigco", plan="enterprise")

    added = client.post(
        "/tenants/bigco/domains",
        json={"host": "erp.bigco.cm"},
        headers=auth_header(owner_token),
    )
    assert added.status_code == 200
    assert any(d["host"] == "erp.bigco.cm" for d in added.json()["domains"])

    # Unverified domains must not get a certificate.
    assert client.get("/internal/tls/check", params={"domain": "erp.bigco.cm"}).status_code == 403
    # Nor must a domain we have never heard of.
    assert client.get("/internal/tls/check", params={"domain": "evil.example"}).status_code == 403

    client.post(
        "/tenants/bigco/domains/erp.bigco.cm/verify", headers=auth_header(owner_token)
    ).raise_for_status()
    assert client.get("/internal/tls/check", params={"domain": "erp.bigco.cm"}).status_code == 200

    # The platform subdomain is verified at creation.
    assert client.get("/internal/tls/check", params={"domain": "bigco.equimed.test"}).status_code == 200


def test_a_domain_cannot_be_claimed_by_two_tenants(client, owner_token, new_tenant):
    new_tenant("firstclaim", plan="enterprise")
    new_tenant("secondclaim", plan="enterprise")
    client.post(
        "/tenants/firstclaim/domains",
        json={"host": "shared.example.cm"},
        headers=auth_header(owner_token),
    ).raise_for_status()
    resp = client.post(
        "/tenants/secondclaim/domains",
        json={"host": "shared.example.cm"},
        headers=auth_header(owner_token),
    )
    assert resp.status_code == 409


def test_last_domain_cannot_be_removed(client, owner_token, new_tenant):
    new_tenant("onedomain")
    resp = client.delete(
        "/tenants/onedomain/domains/onedomain.equimed.test",
        headers=auth_header(owner_token),
    )
    assert resp.status_code == 409


def test_archived_tenant_loses_tls_authorisation(client, owner_token, new_tenant):
    new_tenant("shuttered")
    assert client.get("/internal/tls/check", params={"domain": "shuttered.equimed.test"}).status_code == 200
    client.post("/tenants/shuttered/archive", headers=auth_header(owner_token)).raise_for_status()
    assert client.get("/internal/tls/check", params={"domain": "shuttered.equimed.test"}).status_code == 403


# --- Plans ----------------------------------------------------------------
def test_plan_in_use_cannot_be_deactivated(client, owner_token, new_tenant):
    new_tenant("planuser", plan="starter")
    resp = client.patch(
        "/plans/starter", json={"is_active": False}, headers=auth_header(owner_token)
    )
    assert resp.status_code == 409
    assert "move them" in resp.json()["detail"]


def test_unknown_feature_is_rejected(client, owner_token):
    resp = client.post(
        "/plans",
        json={"code": "bogus", "name": "Bogus", "features": ["mind-reading"]},
        headers=auth_header(owner_token),
    )
    assert resp.status_code == 422
