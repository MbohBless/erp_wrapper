"""Branding validation tests.

Theme values are rendered into a ``<style>`` block on every page, so the
validation in ``schemas.branding`` is a security control, not input hygiene.
The injection cases below are the reason it rejects rather than sanitises.
"""

import pytest
from pydantic import ValidationError

from schemas.branding import (
    DEFAULT_DASHBOARD,
    BrandingUpdate,
    DashboardLayout,
)
from tests.conftest import auth_header


# --- Theme token validation ----------------------------------------------
def test_valid_tokens_are_accepted():
    b = BrandingUpdate(light_tokens={"--color-accent": "#0f766e", "--ok": "#16a34a"})
    assert b.light_tokens["--color-accent"] == "#0f766e"


def test_unknown_token_name_is_rejected():
    with pytest.raises(ValidationError, match="Unknown theme token"):
        BrandingUpdate(light_tokens={"--evil": "#000000"})


@pytest.mark.parametrize(
    "payload",
    [
        # Close the declaration and open a new rule.
        "#fff; } body { background: url(https://evil.example/x.png)",
        # Exfiltrate via a CSS image reference.
        "url(https://evil.example/pixel.png)",
        # Escape through a comment.
        "#fff */ } html { display: none } /*",
        # Expression-style payloads and plain junk.
        "expression(alert(1))",
        "red",
        "",
    ],
)
def test_css_injection_payloads_are_rejected(payload):
    """A token value that is not a bare hex colour cannot leave its declaration."""
    with pytest.raises(ValidationError):
        BrandingUpdate(light_tokens={"--color-accent": payload})


def test_font_family_rejects_declaration_escapes():
    with pytest.raises(ValidationError):
        BrandingUpdate(font_heading="Inter; } body { display:none")
    with pytest.raises(ValidationError):
        BrandingUpdate(font_body="url(https://evil.example/f.woff2)")
    # A real family name still works.
    assert BrandingUpdate(font_heading="IBM Plex Sans").font_heading == "IBM Plex Sans"


def test_assets_must_be_inline_data_uris():
    """Remote asset URLs are refused: branding must not phone home."""
    with pytest.raises(ValidationError):
        BrandingUpdate(logo_light_data_url="https://evil.example/logo.png")
    with pytest.raises(ValidationError):
        BrandingUpdate(favicon_data_url="javascript:alert(1)")
    ok = BrandingUpdate(logo_light_data_url="data:image/png;base64,iVBORw0KGgo=")
    assert ok.logo_light_data_url.startswith("data:image/png")


def test_oversized_asset_is_rejected():
    huge = "data:image/png;base64," + ("A" * (512 * 1024 + 10))
    with pytest.raises(ValidationError, match="too large"):
        BrandingUpdate(logo_light_data_url=huge)


# --- Dashboard layout validation ------------------------------------------
def test_default_dashboard_is_valid_and_covers_the_core_widgets():
    ids = {w.id for w in DEFAULT_DASHBOARD.widgets}
    assert "kpi.revenue" in ids
    assert "chart.revenue_trend" in ids


def test_unknown_widget_is_rejected():
    with pytest.raises(ValidationError):
        DashboardLayout(widgets=[{"id": "kpi.not_a_widget"}])


def test_viz_must_suit_the_widget():
    # A trend chart can be a bar chart...
    assert DashboardLayout(widgets=[{"id": "chart.revenue_trend", "viz": "bar"}])
    # ...but not a donut.
    with pytest.raises(ValidationError, match="supports viz"):
        DashboardLayout(widgets=[{"id": "chart.revenue_trend", "viz": "donut"}])
    # And a KPI tile has no visualisation at all.
    with pytest.raises(ValidationError, match="does not support"):
        DashboardLayout(widgets=[{"id": "kpi.revenue", "viz": "line"}])


def test_duplicate_widgets_are_rejected():
    with pytest.raises(ValidationError, match="Duplicate"):
        DashboardLayout(
            widgets=[{"id": "kpi.revenue"}, {"id": "kpi.revenue", "span": 2}]
        )


def test_span_is_bounded():
    with pytest.raises(ValidationError):
        DashboardLayout(widgets=[{"id": "kpi.revenue", "span": 9}])


# --- Endpoint behaviour (single-tenant app fixture) ------------------------
def test_branding_endpoint_returns_defaults(client, admin_token):
    resp = client.get("/settings/branding", headers=auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["app_name"]
    assert body["dashboard"]["widgets"], "an uncustomised tenant gets the default layout"


def test_branding_update_rejects_injection_over_http(client, admin_token):
    resp = client.put(
        "/settings/branding",
        json={"light_tokens": {"--color-accent": "#fff; } html { display:none"}},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422


def test_branding_roundtrip_over_http(client, admin_token):
    resp = client.put(
        "/settings/branding",
        json={
            "app_name": "Northwind Medical",
            "short_name": "Northwind",
            "light_tokens": {"--color-accent": "#7c3aed"},
            "dark_tokens": {"--color-accent": "#c4b5fd"},
            "font_heading": "IBM Plex Sans",
            "default_theme": "dark",
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["app_name"] == "Northwind Medical"
    assert body["light_tokens"] == {"--color-accent": "#7c3aed"}

    public = client.get("/public/branding")
    assert public.status_code == 200
    assert public.json()["app_name"] == "Northwind Medical"
    assert public.json()["default_theme"] == "dark"


def test_dashboard_reset_restores_the_default(client, admin_token):
    client.put(
        "/settings/branding/dashboard",
        json={"widgets": [{"id": "kpi.revenue", "span": 4}]},
        headers=auth_header(admin_token),
    ).raise_for_status()

    resp = client.post(
        "/settings/branding/dashboard/reset", headers=auth_header(admin_token)
    )
    assert resp.status_code == 200
    assert len(resp.json()["dashboard"]["widgets"]) == len(DEFAULT_DASHBOARD.widgets)
