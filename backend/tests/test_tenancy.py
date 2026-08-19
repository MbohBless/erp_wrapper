"""Tenant isolation tests.

These are the load-bearing tests of the SaaS plane. Everything else in the
suite proves a feature works; these prove that one customer cannot reach
another's data. Treat a failure here as a security incident, not a bug.

All tenants below share one SQLite database on purpose — that is the hostile
case. If isolation holds on a shared database it holds on separate ones.
"""

import pytest
from fastapi.testclient import TestClient

from tenancy import TenantContext

INTERNAL_TOKEN = "test-internal-token"

TENANT_A = TenantContext(
    id="acme",
    name="Acme Medical",
    erpnext_url="http://erp-a.internal:8080",
    erpnext_site="acme.erp.local",
    erpnext_api_key="key-a",
    erpnext_api_secret="secret-a",
    features=frozenset({"branding", "dashboard_layout"}),
)
TENANT_B = TenantContext(
    id="borealis",
    name="Borealis Health",
    erpnext_url="http://erp-b.internal:8080",
    erpnext_site="borealis.erp.local",
    erpnext_api_key="key-b",
    erpnext_api_secret="secret-b",
    features=frozenset({"branding"}),  # deliberately no dashboard_layout
)
TENANT_SUSPENDED = TenantContext(
    id="lapsed", name="Lapsed Clinic", status="suspended"
)
TENANT_PROVISIONING = TenantContext(
    id="fresh", name="Fresh Clinic", status="provisioning"
)

HOSTS = {
    "acme.equimed.test": TENANT_A,
    "borealis.equimed.test": TENANT_B,
    "lapsed.equimed.test": TENANT_SUSPENDED,
    "fresh.equimed.test": TENANT_PROVISIONING,
}


class FakeResolver:
    """Stands in for the control plane: a fixed host -> tenant table."""

    def __init__(self, hosts: dict[str, TenantContext]) -> None:
        self.hosts = hosts
        self.calls: list[str] = []

    async def resolve(self, host: str) -> TenantContext | None:
        self.calls.append(host)
        return self.hosts.get(host.split(":", 1)[0].lower())


@pytest.fixture(scope="module")
def saas_app():
    """A multi-tenant app instance with a stubbed tenant directory."""
    from config import settings
    from main import create_app

    previous_mode = settings.tenancy_mode
    previous_token = settings.internal_api_token
    settings.tenancy_mode = "multi"
    settings.internal_api_token = INTERNAL_TOKEN
    app = create_app(resolver=FakeResolver(HOSTS))
    try:
        with TestClient(app, base_url="http://acme.equimed.test"):
            yield app
    finally:
        settings.tenancy_mode = previous_mode
        settings.internal_api_token = previous_token


def host_client(app, host: str) -> TestClient:
    return TestClient(app, base_url=f"http://{host}")


def bootstrap(app, tenant_id: str, email: str, password: str = "tenantpass123"):
    resp = host_client(app, "acme.equimed.test").post(
        f"/internal/tenants/{tenant_id}/bootstrap",
        json={
            "admin_email": email,
            "admin_password": password,
            "admin_name": "Workspace Admin",
            "company_name": f"{tenant_id.title()} Ltd",
        },
        headers={"X-Internal-Token": INTERNAL_TOKEN},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def login(app, host: str, email: str, password: str = "tenantpass123") -> str:
    resp = host_client(app, host).post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Host resolution ------------------------------------------------------
def test_unknown_host_is_rejected(saas_app):
    resp = host_client(saas_app, "nobody.equimed.test").get("/auth/me")
    assert resp.status_code == 404
    assert "nobody.equimed.test" in resp.json()["detail"]


def test_suspended_tenant_is_refused_before_auth(saas_app):
    """A suspended workspace must be refused without a token being examined."""
    resp = host_client(saas_app, "lapsed.equimed.test").get("/auth/me")
    assert resp.status_code == 402
    assert "suspended" in resp.json()["detail"].lower()


def test_provisioning_tenant_is_locked(saas_app):
    resp = host_client(saas_app, "fresh.equimed.test").get("/public/branding")
    assert resp.status_code == 423


def test_health_is_reachable_without_a_tenant(saas_app):
    resp = host_client(saas_app, "nobody.equimed.test").get("/health")
    assert resp.status_code == 200


# --- Cross-tenant isolation -----------------------------------------------
def test_same_email_can_exist_in_two_tenants(saas_app):
    """The unique-per-tenant email constraint: both workspaces get an admin@."""
    a = bootstrap(saas_app, "acme", "admin@shared.example")
    b = bootstrap(saas_app, "borealis", "admin@shared.example")
    assert a["admin_created"] is True
    assert b["admin_created"] is True


def test_token_from_one_tenant_is_rejected_on_another(saas_app):
    """The cross-tenant replay guard — the single most important assertion."""
    bootstrap(saas_app, "acme", "replay@acme.example")
    token = login(saas_app, "acme.equimed.test", "replay@acme.example")

    ok = host_client(saas_app, "acme.equimed.test").get("/auth/me", headers=bearer(token))
    assert ok.status_code == 200

    replayed = host_client(saas_app, "borealis.equimed.test").get(
        "/auth/me", headers=bearer(token)
    )
    assert replayed.status_code == 401


def test_user_list_never_crosses_tenants(saas_app):
    bootstrap(saas_app, "acme", "list-a@acme.example")
    bootstrap(saas_app, "borealis", "list-b@borealis.example")

    token_a = login(saas_app, "acme.equimed.test", "list-a@acme.example")
    users_a = host_client(saas_app, "acme.equimed.test").get(
        "/users", headers=bearer(token_a)
    )
    assert users_a.status_code == 200
    emails = {u["email"] for u in users_a.json()}
    assert "list-a@acme.example" in emails
    assert not any(e.endswith("@borealis.example") for e in emails)


def test_credentials_do_not_work_across_tenants(saas_app):
    """A password valid on one workspace must not authenticate on another."""
    bootstrap(saas_app, "acme", "solo@acme.example")
    resp = host_client(saas_app, "borealis.equimed.test").post(
        "/auth/login", data={"username": "solo@acme.example", "password": "tenantpass123"}
    )
    assert resp.status_code == 401


def test_branding_is_per_tenant(saas_app):
    bootstrap(saas_app, "acme", "brand-a@acme.example")
    bootstrap(saas_app, "borealis", "brand-b@borealis.example")
    token_a = login(saas_app, "acme.equimed.test", "brand-a@acme.example")
    token_b = login(saas_app, "borealis.equimed.test", "brand-b@borealis.example")

    host_client(saas_app, "acme.equimed.test").put(
        "/settings/branding",
        json={"app_name": "AcmeCare", "light_tokens": {"--color-accent": "#0f766e"}},
        headers=bearer(token_a),
    ).raise_for_status()

    b = host_client(saas_app, "borealis.equimed.test").get(
        "/settings/branding", headers=bearer(token_b)
    )
    assert b.status_code == 200
    assert b.json()["app_name"] != "AcmeCare"

    a = host_client(saas_app, "acme.equimed.test").get(
        "/settings/branding", headers=bearer(token_a)
    )
    assert a.json()["app_name"] == "AcmeCare"
    assert a.json()["light_tokens"]["--color-accent"] == "#0f766e"


# --- ERPNext routing ------------------------------------------------------
def test_erpnext_client_is_built_from_the_request_tenant():
    """Each tenant's client must carry its own credentials and site header."""
    from integrations.erpnext import get_erpnext_client
    from tenancy import reset_current_tenant, set_current_tenant

    token = set_current_tenant(TENANT_A)
    try:
        client = get_erpnext_client()
        assert client.base_url == "http://erp-a.internal:8080"
        assert client.site_host == "acme.erp.local"
        headers = client._headers()
        assert headers["Authorization"] == "token key-a:secret-a"
        assert headers["Host"] == "acme.erp.local"
    finally:
        reset_current_tenant(token)

    token = set_current_tenant(TENANT_B)
    try:
        client = get_erpnext_client()
        assert client.base_url == "http://erp-b.internal:8080"
        assert client._headers()["Authorization"] == "token key-b:secret-b"
    finally:
        reset_current_tenant(token)


# --- Plan / feature gating ------------------------------------------------
def test_feature_gate_blocks_a_plan_without_the_capability(saas_app):
    bootstrap(saas_app, "borealis", "gate@borealis.example")
    token = login(saas_app, "borealis.equimed.test", "gate@borealis.example")
    resp = host_client(saas_app, "borealis.equimed.test").put(
        "/settings/branding/dashboard",
        json={"widgets": [{"id": "kpi.revenue", "span": 1}]},
        headers=bearer(token),
    )
    assert resp.status_code == 402
    assert "dashboard_layout" in resp.json()["detail"]


def test_feature_gate_allows_a_plan_with_the_capability(saas_app):
    bootstrap(saas_app, "acme", "gate@acme.example")
    token = login(saas_app, "acme.equimed.test", "gate@acme.example")
    resp = host_client(saas_app, "acme.equimed.test").put(
        "/settings/branding/dashboard",
        json={"widgets": [{"id": "kpi.revenue", "span": 2}]},
        headers=bearer(token),
    )
    assert resp.status_code == 200
    assert resp.json()["dashboard"]["widgets"] == [
        {"id": "kpi.revenue", "visible": True, "span": 2, "viz": None, "title": None}
    ]


# --- Internal API ---------------------------------------------------------
def test_internal_api_requires_the_shared_secret(saas_app):
    resp = host_client(saas_app, "acme.equimed.test").post(
        "/internal/tenants/acme/bootstrap",
        json={"admin_email": "nope@acme.example", "admin_password": "password123"},
    )
    assert resp.status_code == 401


def test_bootstrap_is_idempotent(saas_app):
    first = bootstrap(saas_app, "acme", "idem@acme.example")
    second = bootstrap(saas_app, "acme", "idem@acme.example")
    assert first["admin_created"] is True
    assert second["admin_created"] is False


def test_purge_removes_only_the_named_tenant(saas_app):
    bootstrap(saas_app, "acme", "keep@acme.example")
    bootstrap(saas_app, "borealis", "purge-me@borealis.example")

    resp = host_client(saas_app, "acme.equimed.test").delete(
        "/internal/tenants/borealis",
        headers={"X-Internal-Token": INTERNAL_TOKEN},
    )
    assert resp.status_code == 200
    assert resp.json()["users_deleted"] >= 1

    # Borealis logins are gone...
    gone = host_client(saas_app, "borealis.equimed.test").post(
        "/auth/login",
        data={"username": "purge-me@borealis.example", "password": "tenantpass123"},
    )
    assert gone.status_code == 401
    # ...and Acme is untouched.
    assert login(saas_app, "acme.equimed.test", "keep@acme.example")


# --- Public (pre-login) branding ------------------------------------------
def test_public_branding_needs_no_token_but_needs_a_known_host(saas_app):
    bootstrap(saas_app, "acme", "public@acme.example")
    ok = host_client(saas_app, "acme.equimed.test").get("/public/branding")
    assert ok.status_code == 200
    assert ok.json()["tenant"] == "acme"
    # No secrets in the pre-login projection.
    assert "support_email" not in ok.json()
    assert "dashboard" not in ok.json()

    unknown = host_client(saas_app, "nobody.equimed.test").get("/public/branding")
    assert unknown.status_code == 404


def test_audit_log_never_crosses_tenants(saas_app):
    """Required for every new tenant-scoped table (see CLAUDE.md).

    The audit log is a particularly bad one to leak: it records who did what and
    from which address, so a cross-tenant read hands over another customer's
    staff list and activity pattern in one request.
    """
    bootstrap(saas_app, "acme", "audit-a@acme.example")
    bootstrap(saas_app, "borealis", "audit-b@borealis.example")

    token_a = login(saas_app, "acme.equimed.test", "audit-a@acme.example")
    token_b = login(saas_app, "borealis.equimed.test", "audit-b@borealis.example")

    # Generate a distinctive mutation in each workspace.
    host_client(saas_app, "acme.equimed.test").post(
        "/users",
        json={"email": "made-in-acme@acme.example", "full_name": "A",
              "role": "Sales", "password": "acmepass12345"},
        headers=bearer(token_a),
    )
    host_client(saas_app, "borealis.equimed.test").post(
        "/users",
        json={"email": "made-in-borealis@borealis.example", "full_name": "B",
              "role": "Sales", "password": "borealispass123"},
        headers=bearer(token_b),
    )

    events_a = host_client(saas_app, "acme.equimed.test").get(
        "/audit", headers=bearer(token_a)
    )
    assert events_a.status_code == 200, events_a.text
    blob_a = str(events_a.json())
    assert "acme.example" in blob_a
    assert "borealis" not in blob_a, "acme can see borealis activity in the audit log"

    events_b = host_client(saas_app, "borealis.equimed.test").get(
        "/audit", headers=bearer(token_b)
    )
    assert events_b.status_code == 200
    blob_b = str(events_b.json())
    assert "borealis.example" in blob_b
    assert "acme" not in blob_b, "borealis can see acme activity in the audit log"
