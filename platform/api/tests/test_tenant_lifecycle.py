"""Tenant lifecycle: create -> provision -> suspend -> resume -> archive -> purge."""

from tests.conftest import auth_header, internal_header


def test_health_is_public(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_new_tenant_starts_pending_with_a_platform_subdomain(client, new_tenant):
    tenant = new_tenant("acme")["tenant"]
    assert tenant["status"] == "pending"
    assert tenant["primary_host"] == "acme.equimed.test"
    # Coordinates are derived so an operator does not have to know the layout.
    assert tenant["erpnext_site"] == "acme.erp.local"


def test_a_pending_tenant_serves_no_traffic(client, owner_token, new_tenant):
    """Resolution reports the real status; the tenant app turns that into a 423."""
    new_tenant("pendingco")
    resp = client.get(
        "/internal/tenants/resolve",
        params={"host": "pendingco.equimed.test"},
        headers=internal_header(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_provision_activates_and_bootstraps(client, owner_token, new_tenant, tenant_app_stub):
    made = new_tenant("northwind")
    resp = client.post(
        f"/tenants/northwind/provision",
        json=made["payload"],
        headers=auth_header(owner_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provisioned"] is True
    assert body["bootstrapped"] is True
    assert body["tenant"]["status"] == "active"
    assert body["tenant"]["provisioned_at"] is not None
    assert "northwind" in tenant_app_stub.bootstrapped


def test_provision_leaves_status_untouched_when_bootstrap_fails(
    client, owner_token, new_tenant, tenant_app_stub
):
    """A half-provisioned workspace must stay locked, never silently active."""
    made = new_tenant("halfway")
    tenant_app_stub.fail_bootstrap = True
    try:
        resp = client.post(
            "/tenants/halfway/provision",
            json=made["payload"],
            headers=auth_header(owner_token),
        )
        assert resp.status_code == 502
    finally:
        tenant_app_stub.fail_bootstrap = False

    after = client.get("/tenants/halfway", headers=auth_header(owner_token)).json()
    assert after["status"] == "provisioning"
    assert after["provisioned_at"] is None


def test_suspend_and_resume(client, owner_token, new_tenant):
    made = new_tenant("lapsed")
    client.post(
        "/tenants/lapsed/provision", json=made["payload"], headers=auth_header(owner_token)
    ).raise_for_status()

    suspended = client.post(
        "/tenants/lapsed/suspend",
        json={"reason": "Invoice 42 unpaid"},
        headers=auth_header(owner_token),
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    assert suspended.json()["suspended_reason"] == "Invoice 42 unpaid"

    # The tenant app sees the suspension through resolution.
    resolved = client.get(
        "/internal/tenants/resolve",
        params={"host": "lapsed.equimed.test"},
        headers=internal_header(),
    )
    assert resolved.json()["status"] == "suspended"

    resumed = client.post("/tenants/lapsed/resume", headers=auth_header(owner_token))
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"
    assert resumed.json()["suspended_reason"] == ""


def test_resume_refuses_a_workspace_that_was_never_provisioned(
    client, owner_token, new_tenant
):
    new_tenant("neverran")
    client.post(
        "/tenants/neverran/suspend", json={"reason": "held"}, headers=auth_header(owner_token)
    ).raise_for_status()
    resp = client.post("/tenants/neverran/resume", headers=auth_header(owner_token))
    assert resp.status_code == 409
    assert "provision" in resp.json()["detail"].lower()


def test_purge_requires_archive_then_matching_confirmation(
    client, owner_token, new_tenant, tenant_app_stub
):
    made = new_tenant("goodbye")
    client.post(
        "/tenants/goodbye/provision", json=made["payload"], headers=auth_header(owner_token)
    ).raise_for_status()

    # Not archived yet.
    too_soon = client.delete(
        "/tenants/goodbye", params={"confirm": "goodbye"}, headers=auth_header(owner_token)
    )
    assert too_soon.status_code == 409

    client.post("/tenants/goodbye/archive", headers=auth_header(owner_token)).raise_for_status()

    # Wrong confirmation.
    wrong = client.delete(
        "/tenants/goodbye", params={"confirm": "goodby"}, headers=auth_header(owner_token)
    )
    assert wrong.status_code == 400

    ok = client.delete(
        "/tenants/goodbye", params={"confirm": "goodbye"}, headers=auth_header(owner_token)
    )
    assert ok.status_code == 200
    assert "goodbye" in tenant_app_stub.purged
    assert client.get("/tenants/goodbye", headers=auth_header(owner_token)).status_code == 404


def test_duplicate_workspace_id_is_rejected(client, owner_token, new_tenant):
    new_tenant("twice")
    resp = client.post(
        "/tenants",
        json={
            "id": "twice",
            "name": "Duplicate Co",
            "plan_code": "starter",
            "admin_email": "admin@twice.example",
            "admin_password": "workspacepass123",
        },
        headers=auth_header(owner_token),
    )
    assert resp.status_code == 409


def test_reserved_and_malformed_slugs_are_rejected(client, owner_token):
    # Reserved subdomains would shadow platform infrastructure; the rest are
    # not valid DNS labels.
    for slug in ("api", "www", "admin", "platform", "-leading", "trailing-", "x", "has_underscore"):
        resp = client.post(
            "/tenants",
            json={
                "id": slug,
                "name": "Nope Co",
                "plan_code": "starter",
                "admin_email": "admin@nope.example",
                "admin_password": "workspacepass123",
            },
            headers=auth_header(owner_token),
        )
        assert resp.status_code == 422, f"{slug} should have been rejected"


def test_slug_case_is_normalised(client, owner_token):
    """Slugs become subdomains and ERPNext site names, so they are lowercased
    rather than rejected — DNS is case-insensitive and one canonical form
    keeps the tenant id identical across all three layers."""
    resp = client.post(
        "/tenants",
        json={
            "id": "Mixed-Case",
            "name": "Mixed Case Co",
            "plan_code": "starter",
            "admin_email": "admin@mixed.example",
            "admin_password": "workspacepass123",
        },
        headers=auth_header(owner_token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["id"] == "mixed-case"
    assert resp.json()["primary_host"] == "mixed-case.equimed.test"


def test_unknown_plan_is_rejected(client, owner_token):
    resp = client.post(
        "/tenants",
        json={
            "id": "planless",
            "name": "Planless Co",
            "plan_code": "does-not-exist",
            "admin_email": "admin@planless.example",
            "admin_password": "workspacepass123",
        },
        headers=auth_header(owner_token),
    )
    assert resp.status_code == 422


def test_stats_counts_by_status(client, owner_token):
    resp = client.get("/tenants/stats", headers=auth_header(owner_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert isinstance(body["by_status"], dict)


def test_audit_log_records_every_transition(client, owner_token, new_tenant):
    made = new_tenant("audited")
    client.post(
        "/tenants/audited/provision", json=made["payload"], headers=auth_header(owner_token)
    ).raise_for_status()
    client.post(
        "/tenants/audited/suspend", json={"reason": "test"}, headers=auth_header(owner_token)
    ).raise_for_status()

    resp = client.get(
        "/audit", params={"tenant_id": "audited"}, headers=auth_header(owner_token)
    )
    assert resp.status_code == 200
    actions = {e["action"] for e in resp.json()}
    assert {"tenant.created", "tenant.provisioned", "tenant.suspended"} <= actions
    assert all(e["actor_email"] == "owner@equimed.app" for e in resp.json())
