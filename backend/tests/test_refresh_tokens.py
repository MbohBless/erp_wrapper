"""Session refresh: rotation, revocation, and reuse detection.

Before this, an access token lasted 60 minutes and there was nothing to renew
it with, so a user working for an hour was signed out mid-task. The fix cannot
simply be a longer expiry: a JWT cannot be withdrawn, so a longer one is a
longer window in which a stolen token keeps working.

Hence server-side refresh tokens — revocable, single-use, and family-tracked so
that a replay is detectable at all.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, auth_header, login


def _login(client):
    resp = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_login_returns_a_refresh_token_and_an_expiry(client):
    body = _login(client)
    assert body["access_token"]
    assert body["refresh_token"], "no refresh token: the session cannot be renewed"
    assert body["expires_in"] > 0


def test_refresh_returns_a_working_access_token(client):
    body = _login(client)
    resp = client.post("/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert resp.status_code == 200, resp.text
    fresh = resp.json()
    assert fresh["access_token"]
    me = client.get("/auth/me", headers=auth_header(fresh["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == ADMIN_EMAIL


def test_refresh_rotates_the_token(client):
    """Each refresh token works once; a new one comes back."""
    body = _login(client)
    first = body["refresh_token"]
    second = client.post("/auth/refresh", json={"refresh_token": first}).json()[
        "refresh_token"
    ]
    assert second != first, "the refresh token was not rotated"
    # The new one works…
    assert client.post("/auth/refresh", json={"refresh_token": second}).status_code == 200


def test_a_used_refresh_token_is_rejected(client):
    body = _login(client)
    first = body["refresh_token"]
    client.post("/auth/refresh", json={"refresh_token": first})
    replay = client.post("/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401


def test_replay_kills_the_whole_family(client):
    """Two parties holding one token means one is an attacker.

    We cannot tell which, so both lose the session. Without this, a thief who
    copies a refresh token simply keeps refreshing forever alongside the user.
    """
    body = _login(client)
    stolen = body["refresh_token"]
    legitimate = client.post("/auth/refresh", json={"refresh_token": stolen}).json()[
        "refresh_token"
    ]

    # The attacker replays the token they copied.
    assert client.post("/auth/refresh", json={"refresh_token": stolen}).status_code == 401

    # The legitimate holder's token is now dead too — the session is cut off
    # rather than shared.
    assert (
        client.post("/auth/refresh", json={"refresh_token": legitimate}).status_code
        == 401
    )


def test_logout_revokes_the_session(client):
    body = _login(client)
    out = client.post(
        "/auth/logout",
        json={"refresh_token": body["refresh_token"]},
        headers=auth_header(body["access_token"]),
    )
    assert out.status_code == 200
    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": body["refresh_token"]}
        ).status_code
        == 401
    )


def test_garbage_and_empty_tokens_are_rejected(client):
    for value in ("", "not-a-token", "x" * 200):
        assert (
            client.post("/auth/refresh", json={"refresh_token": value}).status_code
            == 401
        )


def test_an_expired_refresh_token_is_rejected(client):
    from database import SessionLocal
    from models.refresh_token import RefreshToken
    from sqlalchemy import select

    body = _login(client)
    db = SessionLocal()
    try:
        row = db.scalars(
            select(RefreshToken).order_by(RefreshToken.id.desc())
        ).first()
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": body["refresh_token"]}
        ).status_code
        == 401
    )


def test_the_raw_token_is_never_stored(client):
    """A backup or stray query must not hand out working sessions."""
    from database import SessionLocal
    from models.refresh_token import RefreshToken
    from sqlalchemy import select

    body = _login(client)
    raw = body["refresh_token"]
    db = SessionLocal()
    try:
        hashes = list(db.scalars(select(RefreshToken.token_hash)))
    finally:
        db.close()
    assert raw not in hashes
    assert all(len(h) == 64 for h in hashes), "expected SHA-256 hex digests"


def test_a_deactivated_user_cannot_refresh(client, admin_token):
    """Disabling an account must end its sessions, not just block new logins."""
    created = client.post(
        "/users",
        json={"email": "soon-disabled@equimed.cm", "full_name": "D",
              "role": "Sales", "password": "disabledpass1"},
        headers=auth_header(admin_token),
    )
    assert created.status_code == 201
    uid = created.json()["id"]

    session = login(client, "soon-disabled@equimed.cm", "disabledpass1").json()
    assert client.post(
        "/auth/refresh", json={"refresh_token": session["refresh_token"]}
    ).status_code == 200

    client.put(
        f"/users/{uid}", json={"is_active": False}, headers=auth_header(admin_token)
    )
    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": session["refresh_token"]}
        ).status_code
        == 401
    )
