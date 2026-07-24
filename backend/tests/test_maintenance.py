"""Integration tests for the Maintenance module (tickets: CRUD + complete + RBAC)."""

from tests.conftest import auth_header

TICKET = {
    "customer": "CHU Yaoundé",
    "equipment": "VENT-0001",
    "engineer": "Eng. Talla",
    "visit_date": "2026-09-18",
    "description": "Ventilator calibration",
    "status": "Scheduled",
}


def _create(client, token, **overrides):
    return client.post(
        "/maintenance", json={**TICKET, **overrides}, headers=auth_header(token)
    )


def test_create_ticket(client, admin_token, fake_erpnext):
    resp = _create(client, admin_token)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"].startswith("Maintenance Visit")
    assert body["status"] == "Scheduled"
    assert body["engineer"] == "Eng. Talla"

    stored = fake_erpnext.store[body["id"]]
    assert stored["customer"] == "CHU Yaoundé"
    assert stored["custom_serial_no"] == "VENT-0001"
    assert stored["custom_engineer"] == "Eng. Talla"


def test_list_search_and_status_filter(client, admin_token, fake_erpnext):
    _create(client, admin_token, customer="Hôpital Général Douala")
    _create(client, admin_token, customer="Clinique du Littoral", status="Open")

    resp = client.get(
        "/maintenance", params={"search": "Douala"}, headers=auth_header(admin_token)
    )
    assert {t["customer"] for t in resp.json()} == {"Hôpital Général Douala"}

    resp = client.get(
        "/maintenance", params={"status": "Open"}, headers=auth_header(admin_token)
    )
    assert all(t["status"] == "Open" for t in resp.json())
    assert len(resp.json()) == 1


def test_complete_action_captures_signature(client, admin_token, fake_erpnext):
    ticket = _create(client, admin_token).json()
    resp = client.post(
        f"/maintenance/{ticket['id']}/complete",
        json={"parts_used": "Flow sensor, O2 cell", "signed": True},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "Completed"
    assert body["customer_signed"] is True
    assert body["parts_used"] == "Flow sensor, O2 cell"


def test_update_and_delete(client, admin_token, fake_erpnext):
    ticket = _create(client, admin_token).json()
    upd = client.put(
        f"/maintenance/{ticket['id']}",
        json={"status": "In Progress"},
        headers=auth_header(admin_token),
    )
    assert upd.status_code == 200 and upd.json()["status"] == "In Progress"
    assert client.delete(f"/maintenance/{ticket['id']}", headers=auth_header(admin_token)).status_code == 204
    assert client.get(f"/maintenance/{ticket['id']}", headers=auth_header(admin_token)).status_code == 404


# --- RBAC ---


def test_biomedical_can_manage(client, make_token, fake_erpnext):
    token = make_token("Biomedical Engineer")
    assert _create(client, token).status_code == 201


def test_sales_can_view_but_not_manage(client, admin_token, make_token, fake_erpnext):
    _create(client, admin_token)
    token = make_token("Sales")
    assert client.get("/maintenance", headers=auth_header(token)).status_code == 200
    assert _create(client, token).status_code == 403


def test_store_keeper_cannot_view(client, make_token, fake_erpnext):
    token = make_token("Store Keeper")
    assert client.get("/maintenance", headers=auth_header(token)).status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/maintenance").status_code == 401
