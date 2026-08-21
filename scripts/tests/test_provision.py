"""Tests for the provisioner's two dangerous jobs: reading a config it should
refuse, and editing a .env it must not corrupt.

Neither is exercised by running it — a provisioning run takes ten minutes and
ends with a live site — so the parts that decide whether it *should* run are
tested here instead.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "provision", ROOT / "scripts" / "provision.py"
)
provision = importlib.util.module_from_spec(spec)
sys.modules["provision"] = provision
spec.loader.exec_module(provision)


GOOD = """
site: {domain: app.acme.com, erpnext_site: acme.local}
company:
  name: Acme Medical Sarl
  abbrev: AMS
  country: Cameroon
  timezone: Africa/Douala
  currency: XAF
  chart_of_accounts: SYSCOHADA
  fiscal_year_start: "2026-01-01"
  fiscal_year_end: "2026-12-31"
erpnext_admin: {email: admin@acme.com, full_name: Administrator}
integration_user: {email: bot@acme.com}
app_admin: {email: admin@acme.com, full_name: Administrator}
"""


def write(tmp_path, text, name="c.yml"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_a_complete_config_is_accepted(tmp_path):
    cfg = provision.load_config(write(tmp_path, GOOD))
    assert cfg["company"]["abbrev"] == "AMS"


def test_a_missing_abbreviation_stops_provisioning(tmp_path, capsys):
    """The field is set_only_once and is suffixed onto ~1,400 account names.
    Letting ERPNext derive it is how a deployment ends up needing a rebuild to
    change a three-letter string."""
    bad = GOOD.replace("  abbrev: AMS\n", "")
    with pytest.raises(SystemExit):
        provision.load_config(write(tmp_path, bad))
    assert "company.abbrev" in capsys.readouterr().err


@pytest.mark.parametrize("abbrev", ["A M S", "way-too-long-abbrev", "AM/S", "Ams Sarl"])
def test_an_unusable_abbreviation_is_refused(tmp_path, capsys, abbrev):
    bad = GOOD.replace("abbrev: AMS", f"abbrev: {abbrev!r}")
    with pytest.raises(SystemExit):
        provision.load_config(write(tmp_path, bad))
    assert "abbrev" in capsys.readouterr().err


def test_a_secret_in_the_config_is_refused(tmp_path, capsys):
    """The config is meant to be committed. Provisioning generates credentials
    and writes them to .env precisely so this file never holds one."""
    bad = GOOD.replace(
        "erpnext_admin: {email: admin@acme.com, full_name: Administrator}",
        "erpnext_admin: {email: admin@acme.com, full_name: Administrator, "
        "password: hunter2}",
    )
    with pytest.raises(SystemExit):
        provision.load_config(write(tmp_path, bad))
    err = capsys.readouterr().err
    assert "must not be in the config" in err


def test_every_missing_field_is_reported_at_once(tmp_path, capsys):
    """Not one per run. A ten-minute build is a bad way to discover the second
    typo."""
    with pytest.raises(SystemExit):
        provision.load_config(write(tmp_path, "site: {domain: x}"))
    err = capsys.readouterr().err
    assert "site.erpnext_site" in err and "missing section: company" in err


# --- .env ----------------------------------------------------------------


@pytest.fixture()
def env(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.setattr(provision, "ENV", path)
    return path


def test_values_are_read_not_executed(env):
    """.env is a key/value file. Sourcing it *executes* it, so a company name
    with an ampersand backgrounds a process and tries to run the second word."""
    env.write_text(
        'BRAND_APP_NAME=Biomedical Equipment & Supplies\n'
        'QUOTED="has spaces"\n'
        '# a comment\n'
        '\n'
        'EMPTY=\n',
        encoding="utf-8",
    )
    values = provision.env_read()
    assert values["BRAND_APP_NAME"] == "Biomedical Equipment & Supplies"
    assert values["QUOTED"] == "has spaces"
    assert values["EMPTY"] == ""
    assert "# a comment" not in values


def test_writing_a_key_leaves_the_rest_of_the_file_alone(env):
    env.write_text(
        "# Secrets — do not regenerate\n"
        "JWT_SECRET_KEY=keep-me\n"
        "SITE_NAME=old.local\n",
        encoding="utf-8",
    )
    provision.env_write({"SITE_NAME": "new.local"})
    text = env.read_text(encoding="utf-8")
    assert "SITE_NAME=new.local" in text
    assert "JWT_SECRET_KEY=keep-me" in text
    assert "# Secrets — do not regenerate" in text
    assert "old.local" not in text


def test_a_new_key_is_appended_and_a_commented_one_is_revived(env):
    env.write_text("SITE_NAME=x\n#DISABLED_ROLES=[]\n", encoding="utf-8")
    provision.env_write({"DISABLED_ROLES": '["Sales"]', "ERPNEXT_API_KEY": "abc"})
    text = env.read_text(encoding="utf-8")
    assert 'DISABLED_ROLES=["Sales"]' in text
    assert "#DISABLED_ROLES" not in text
    assert "ERPNEXT_API_KEY=abc" in text


def test_the_file_is_not_world_readable(env):
    env.write_text("A=1\n", encoding="utf-8")
    provision.env_write({"B": "2"})
    assert oct(os.stat(env).st_mode)[-3:] == "600"


def test_generated_passwords_avoid_characters_that_get_misread(env):
    """They are read off a terminal once and typed into a browser. l/1/I/0/O in
    a password that exists only on someone's screen is a support call."""
    for _ in range(50):
        pw = provision.password()
        assert len(pw) == 16
        assert not set(pw) & set("lI1O0")


# --- Not over a live instance --------------------------------------------
#
# The provisioner rewrites .env, rebuilds the containers and reissues the
# ERPNext API credentials. Aimed at a deployment someone is using, that stops
# them working mid-sentence, with the cause several steps behind the symptom.


def cfg_for(site="acme.local"):
    return {"site": {"erpnext_site": site, "domain": "app.acme.com"}}


def test_a_different_site_in_this_directory_is_a_conflict():
    """Two clients do not share a working tree. Running the second config here
    would point the running stack at a site it was not built for."""
    reason = provision.existing_deployment_conflict(
        cfg_for("acme.local"), {"SITE_NAME": "qbmedicals.local"}
    )
    assert reason and "qbmedicals.local" in reason and "acme.local" in reason


def test_the_same_site_is_not_a_conflict():
    """Re-running against the deployment this directory already describes is
    the resume case, which is supported."""
    assert provision.existing_deployment_conflict(
        cfg_for("acme.local"), {"SITE_NAME": "acme.local"}
    ) is None


def test_an_empty_env_is_not_a_conflict():
    """A first run has nothing to conflict with."""
    assert provision.existing_deployment_conflict(cfg_for(), {}) is None
