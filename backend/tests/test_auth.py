"""Integration tests for authentication and the administrator login."""

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, auth_header, login


def test_admin_login_success(client):
    resp = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password(client):
    resp = login(client, ADMIN_EMAIL, "not-the-password")
    assert resp.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_current_user(client, admin_token):
    resp = client.get("/auth/me", headers=auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == ADMIN_EMAIL
    assert body["role"] == "Administrator"


def test_logout_ok(client, admin_token):
    resp = client.post("/auth/logout", headers=auth_header(admin_token))
    assert resp.status_code == 200
