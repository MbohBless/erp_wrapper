"""Control-plane test configuration.

Environment is set BEFORE any application module is imported so that
``config.Settings`` picks up the throwaway database and seeded owner.
"""

import itertools
import os
import tempfile

# Process-wide so generated operator/workspace identifiers stay unique across
# every test in the session (the seeded database is not reset between tests).
_operator_counter = itertools.count(1)
_tenant_counter = itertools.count(1)

_TMP_DIR = tempfile.mkdtemp(prefix="equimed-platform-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DIR}/platform.db")
os.environ.setdefault("JWT_SECRET_KEY", "platform-test-secret")
os.environ.setdefault("SECRET_ENCRYPTION_KEY", "platform-test-encryption-key")
os.environ.setdefault("INTERNAL_API_TOKEN", "platform-internal-test-token")
os.environ.setdefault("FIRST_OWNER_EMAIL", "owner@equimed.app")
os.environ.setdefault("FIRST_OWNER_PASSWORD", "ownerpassword123")
os.environ.setdefault("FIRST_OWNER_NAME", "Platform Owner")
os.environ.setdefault("BASE_DOMAIN", "equimed.test")
os.environ.setdefault("PROVISIONER", "noop")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

OWNER_EMAIL = os.environ["FIRST_OWNER_EMAIL"]
OWNER_PASSWORD = os.environ["FIRST_OWNER_PASSWORD"]
INTERNAL_TOKEN = os.environ["INTERNAL_API_TOKEN"]


class FakeTenantAppClient:
    """Stands in for a running tenant backend.

    Provisioning is only "done" once the tenant app has an administrator, so
    the control-plane tests need this boundary faked rather than skipped.
    """

    def __init__(self) -> None:
        self.bootstrapped: list[str] = []
        self.purged: list[str] = []
        self.fail_bootstrap = False

    async def bootstrap(self, tenant_id: str, **kwargs) -> dict:
        if self.fail_bootstrap:
            from integrations.tenant_app import TenantAppError

            raise TenantAppError("tenant app is down")
        first_time = tenant_id not in self.bootstrapped
        self.bootstrapped.append(tenant_id)
        return {"tenant_id": tenant_id, "admin_created": first_time,
                "admin_email": kwargs.get("admin_email", "")}

    async def purge(self, tenant_id: str) -> dict:
        self.purged.append(tenant_id)
        return {"tenant_id": tenant_id, "users_deleted": 3}


@pytest.fixture(scope="session")
def tenant_app_stub() -> FakeTenantAppClient:
    return FakeTenantAppClient()


@pytest.fixture(scope="session")
def client(tenant_app_stub):
    from api.deps import get_tenant_app_client
    from main import app

    app.dependency_overrides[get_tenant_app_client] = lambda: tenant_app_stub
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def login(client, email: str, password: str):
    return client.post("/auth/login", data={"username": email, "password": password})


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def internal_header() -> dict:
    return {"X-Internal-Token": INTERNAL_TOKEN}


@pytest.fixture()
def owner_token(client) -> str:
    resp = login(client, OWNER_EMAIL, OWNER_PASSWORD)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def make_operator(client, owner_token):
    """Factory: create an operator with a role, returning id/email/token.

    The counter is process-wide because the seeded database persists for the
    whole session — a per-fixture counter would recycle emails across tests.
    """

    def _make(role: str, password: str = "operatorpassword123") -> dict:
        n = next(_operator_counter)
        # .example, not .test: email-validator refuses special-use TLDs.
        email = f"{role.lower()}-{n}@equimed-ops.example"
        resp = client.post(
            "/operators",
            json={
                "email": email,
                "full_name": f"{role} Operator",
                "password": password,
                "role": role,
            },
            headers=auth_header(owner_token),
        )
        assert resp.status_code == 201, resp.text
        token = login(client, email, password).json()["access_token"]
        return {"id": resp.json()["id"], "email": email, "password": password, "token": token}

    return _make


@pytest.fixture()
def new_tenant(client, owner_token):
    """Factory: register a workspace and return its payload."""
    def _make(slug: str | None = None, plan: str = "enterprise", **overrides) -> dict:
        slug = slug or f"tenant-{next(_tenant_counter)}"
        payload = {
            "id": slug,
            "name": f"{slug.title()} Medical",
            "plan_code": plan,
            "contact_email": f"ops@{slug}.example",
            "admin_email": f"admin@{slug}.example",
            "admin_password": "workspacepass123",
            "admin_name": "Workspace Admin",
            **overrides,
        }
        resp = client.post("/tenants", json=payload, headers=auth_header(owner_token))
        assert resp.status_code == 201, resp.text
        return {"tenant": resp.json(), "payload": payload}

    return _make
