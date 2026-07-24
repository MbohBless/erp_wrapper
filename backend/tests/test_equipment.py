"""Integration tests for the Equipment module (CRUD + install + RBAC)."""

from tests.conftest import auth_header

EQUIPMENT = {
    "serial_no": "VENT-0001",
    "item_code": "VENTILATOR-X",
    "customer": "CHU Yaoundé",
    "warranty_expiry_date": "2028-01-01",
    "status": "In Store",
}


def _create(client, token, **overrides):
    return client.post(
        "/equipment", json={**EQUIPMENT, **overrides}, headers=auth_header(token)
    )


def test_register_and_get(client, admin_token, fake_erpnext):
    resp = _create(client, admin_token)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == "VENT-0001"
    assert body["status"] == "In Store"

    stored = fake_erpnext.store["VENT-0001"]
    assert stored["serial_no"] == "VENT-0001"
    assert stored["custom_status"] == "In Store"

    got = client.get("/equipment/VENT-0001", headers=auth_header(admin_token))
    assert got.status_code == 200
    assert got.json()["customer"] == "CHU Yaoundé"


def test_list_search_and_status_filter(client, admin_token, fake_erpnext):
    _create(client, admin_token, serial_no="MRI-1", item_code="MRI-SCANNER")
    _create(client, admin_token, serial_no="XRAY-9", status="Under Repair")

    resp = client.get("/equipment", params={"search": "MRI"}, headers=auth_header(admin_token))
    assert [e["id"] for e in resp.json()] == ["MRI-1"]

    resp = client.get(
        "/equipment", params={"status": "Under Repair"}, headers=auth_header(admin_token)
    )
    assert {e["id"] for e in resp.json()} == {"XRAY-9"}


def test_install_action(client, admin_token, fake_erpnext):
    _create(client, admin_token, serial_no="ECG-5")
    resp = client.post(
        "/equipment/ECG-5/install",
        json={"installation_date": "2026-09-20", "customer": "Clinique du Littoral"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "Installed"
    assert body["installation_date"] == "2026-09-20"
    assert body["customer"] == "Clinique du Littoral"


def test_update_and_delete(client, admin_token, fake_erpnext):
    _create(client, admin_token, serial_no="DEL-1")
    upd = client.put(
        "/equipment/DEL-1",
        json={"status": "Decommissioned"},
        headers=auth_header(admin_token),
    )
    assert upd.status_code == 200 and upd.json()["status"] == "Decommissioned"
    assert client.delete("/equipment/DEL-1", headers=auth_header(admin_token)).status_code == 204
    assert client.get("/equipment/DEL-1", headers=auth_header(admin_token)).status_code == 404


def test_duplicate_conflict(client, admin_token, fake_erpnext):
    _create(client, admin_token, serial_no="DUP-1")
    assert _create(client, admin_token, serial_no="DUP-1").status_code == 409


# --- RBAC ---


def test_biomedical_can_manage(client, make_token, fake_erpnext):
    token = make_token("Biomedical Engineer")
    assert _create(client, token, serial_no="BIO-1").status_code == 201


def test_sales_can_view_but_not_manage(client, admin_token, make_token, fake_erpnext):
    _create(client, admin_token, serial_no="VIEW-1")
    token = make_token("Sales")
    assert client.get("/equipment", headers=auth_header(token)).status_code == 200
    assert _create(client, token, serial_no="NO-1").status_code == 403


def test_accountant_cannot_view(client, make_token, fake_erpnext):
    token = make_token("Accountant")
    assert client.get("/equipment", headers=auth_header(token)).status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/equipment").status_code == 401
