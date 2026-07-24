"""Test configuration.

Environment is set BEFORE any application module is imported so that
`config.Settings` picks up the test database and seeded admin credentials.
"""

import itertools
import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="equimed-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DIR}/test.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("FIRST_ADMIN_EMAIL", "admin@equimed.cm")
os.environ.setdefault("FIRST_ADMIN_PASSWORD", "admin12345")
os.environ.setdefault("FIRST_ADMIN_NAME", "Administrator")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ADMIN_EMAIL = os.environ["FIRST_ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["FIRST_ADMIN_PASSWORD"]

# Process-wide counter so generated user emails are unique across all tests
# (the seeded SQLite DB persists for the whole session).
_email_counter = itertools.count(1)


@pytest.fixture(scope="session")
def client():
    # Import inside the fixture so env vars above are already applied.
    from main import app

    with TestClient(app) as test_client:  # enter lifespan (create tables + seed)
        yield test_client


def login(client, email: str, password: str):
    return client.post(
        "/auth/login", data={"username": email, "password": password}
    )


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_token(client):
    resp = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def fake_erpnext(client):
    """Override the ERPNext client with an in-memory fake for the test's duration."""
    from integrations.erpnext import get_erpnext_client
    from main import app
    from tests.fakes import FakeERPNextClient

    fake = FakeERPNextClient()
    app.dependency_overrides[get_erpnext_client] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_erpnext_client, None)


@pytest.fixture()
def make_token(client, admin_token):
    """Factory: create a user with a given role (as admin) and return its token."""
    def _make(role: str, password: str = "rolepass123") -> str:
        n = next(_email_counter)
        email = f"role-{role.replace(' ', '-').lower()}-{n}@equimed.cm"
        resp = client.post(
            "/users",
            json={
                "email": email,
                "full_name": f"{role} User",
                "role": role,
                "password": password,
            },
            headers=auth_header(admin_token),
        )
        assert resp.status_code == 201, resp.text
        return login(client, email, password).json()["access_token"]

    return _make
