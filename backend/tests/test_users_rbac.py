"""Integration tests for User CRUD and role-based access control."""

from tests.conftest import auth_header, login


def _create_user(client, admin_token, **overrides):
    payload = {
        "email": "sales1@equimed.cm",
        "full_name": "Sales One",
        "role": "Sales",
        "password": "salespass123",
    }
    payload.update(overrides)
    return client.post("/users", json=payload, headers=auth_header(admin_token))


def test_admin_can_create_and_list_users(client, admin_token):
    resp = _create_user(client, admin_token, email="crud-user@equimed.cm")
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["email"] == "crud-user@equimed.cm"
    assert created["role"] == "Sales"
    assert "password" not in created  # never leak secrets

    listing = client.get("/users", headers=auth_header(admin_token))
    assert listing.status_code == 200
    emails = [u["email"] for u in listing.json()]
    assert "crud-user@equimed.cm" in emails


def test_duplicate_email_conflict(client, admin_token):
    _create_user(client, admin_token, email="dup@equimed.cm")
    resp = _create_user(client, admin_token, email="dup@equimed.cm")
    assert resp.status_code == 409


def test_update_and_delete_user(client, admin_token):
    created = _create_user(
        client, admin_token, email="mutate@equimed.cm"
    ).json()
    uid = created["id"]

    upd = client.put(
        f"/users/{uid}",
        json={"role": "Manager", "full_name": "Renamed"},
        headers=auth_header(admin_token),
    )
    assert upd.status_code == 200
    assert upd.json()["role"] == "Manager"
    assert upd.json()["full_name"] == "Renamed"

    dele = client.delete(f"/users/{uid}", headers=auth_header(admin_token))
    assert dele.status_code == 204
    assert client.get(f"/users/{uid}", headers=auth_header(admin_token)).status_code == 404


def test_non_admin_cannot_manage_users(client, admin_token):
    # Admin provisions a Sales user, who then logs in.
    _create_user(client, admin_token, email="rbac-sales@equimed.cm")
    token = login(client, "rbac-sales@equimed.cm", "salespass123").json()[
        "access_token"
    ]

    # Sales cannot list or create users.
    assert client.get("/users", headers=auth_header(token)).status_code == 403
    create = client.post(
        "/users",
        json={
            "email": "x@equimed.cm",
            "full_name": "X",
            "role": "Sales",
            "password": "whateverpass",
        },
        headers=auth_header(token),
    )
    assert create.status_code == 403


def test_user_can_read_self_but_not_others(client, admin_token):
    me = _create_user(client, admin_token, email="self@equimed.cm").json()
    other = _create_user(client, admin_token, email="other@equimed.cm").json()
    token = login(client, "self@equimed.cm", "salespass123").json()[
        "access_token"
    ]

    assert (
        client.get(f"/users/{me['id']}", headers=auth_header(token)).status_code == 200
    )
    assert (
        client.get(f"/users/{other['id']}", headers=auth_header(token)).status_code
        == 403
    )


def test_unauthenticated_rejected(client):
    assert client.get("/users").status_code == 401
