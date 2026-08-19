"""A deployment can retire a role without the product losing it.

One workspace having no sales reps is no reason for the next one to lose the
option, so this is configuration (DISABLED_ROLES) rather than a code change.
Disabled means the role cannot be *assigned*; its permissions and its tests are
untouched, so re-enabling it is a config edit, not a restoration.
"""

import pytest

from config import get_settings
from models.user import Role, assignable_roles
from tests.conftest import auth_header


@pytest.fixture()
def without_sales():
    """Retire the Sales role for the duration of a test."""
    settings = get_settings()
    original = settings.disabled_roles
    settings.disabled_roles = ["Sales"]
    try:
        yield
    finally:
        settings.disabled_roles = original


def test_every_role_is_assignable_by_default():
    assert set(assignable_roles()) == set(Role)


def test_a_disabled_role_is_not_offered(without_sales):
    assert Role.SALES not in assignable_roles()
    # Only that one. Retiring a role must not quietly narrow the rest.
    assert set(assignable_roles()) == set(Role) - {Role.SALES}


def test_administrator_can_never_be_disabled():
    """A deployment that could disable it could lock itself out of its own user
    administration, with nothing left that can undo the setting."""
    settings = get_settings()
    original = settings.disabled_roles
    settings.disabled_roles = ["Administrator", "Sales"]
    try:
        assert Role.ADMINISTRATOR in assignable_roles()
        assert Role.SALES not in assignable_roles()
    finally:
        settings.disabled_roles = original


def test_the_endpoint_reports_what_may_be_assigned(client, admin_token, without_sales):
    resp = client.get("/users/roles", headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert "Sales" not in resp.json()
    assert "Accountant" in resp.json()


def test_creating_a_user_with_a_retired_role_is_refused(
    client, admin_token, without_sales
):
    """Enforced in the API, not only hidden in the dropdown. A policy only the
    UI knows is one anybody with a terminal can ignore."""
    resp = client.post(
        "/users",
        json={"email": "rep@qbmedicals.cm", "full_name": "Rep",
              "role": "Sales", "password": "whatever123"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422
    assert "not in use on this workspace" in resp.json()["detail"]


def test_promoting_someone_into_a_retired_role_is_refused(
    client, admin_token, without_sales
):
    """The create path is the obvious one; the update path is how it gets in."""
    made = client.post(
        "/users",
        json={"email": "acct2@qbmedicals.cm", "full_name": "Acct",
              "role": "Accountant", "password": "whatever123"},
        headers=auth_header(admin_token),
    ).json()
    resp = client.put(f"/users/{made['id']}", json={"role": "Sales"},
                      headers=auth_header(admin_token))
    assert resp.status_code == 422


def test_a_role_still_in_use_is_unaffected(client, admin_token, without_sales):
    resp = client.post(
        "/users",
        json={"email": "keeper@qbmedicals.cm", "full_name": "Keeper",
              "role": "Store Keeper", "password": "whatever123"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
