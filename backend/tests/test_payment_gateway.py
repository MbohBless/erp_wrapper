"""Gateway orchestration: request money, confirm it, post it to the ledger.

These cover the behaviour that costs real money when it is wrong — double
charges, payments lost between provider and ledger, and callbacks that lie.
Everything runs against the fake provider and a fake ERPNext, so no credentials
are needed and nothing leaves the machine.
"""

import itertools
import json

import pytest

from integrations.payments.fake import FakePaymentProvider
from tests.conftest import auth_header

_invoice_seq = itertools.count(1)


@pytest.fixture(autouse=True)
def _reset_fake_provider():
    FakePaymentProvider.reset()
    yield
    FakePaymentProvider.reset()


@pytest.fixture()
def gateway(client, admin_token, fake_erpnext):
    """An activated fake provider plus a helper to seed invoices."""
    resp = client.put(
        "/gateway/providers",
        json={"provider": "fake", "mode": "sandbox", "credentials": {}, "activate": True},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200, resp.text

    def seed_invoice(outstanding: int = 5000, doctype: str = "Sales Invoice") -> str:
        name = f"{'SI' if doctype == 'Sales Invoice' else 'PI'}-{next(_invoice_seq):04d}"
        fake_erpnext.store[name] = {
            "name": name,
            "doctype": doctype,
            "docstatus": 1,
            "outstanding_amount": outstanding,
            "grand_total": outstanding,
            "currency": "XAF",
            "customer" if doctype == "Sales Invoice" else "supplier": "Acme Ltd",
        }
        return name

    return seed_invoice


def collect(client, token, **kwargs):
    return client.post("/gateway/collections", json=kwargs, headers=auth_header(token))


def refresh(client, token, intent_id: int):
    return client.get(
        f"/gateway/payments/{intent_id}", params={"refresh": True}, headers=auth_header(token)
    )


# --- Provider configuration ----------------------------------------------
def test_credentials_go_in_and_never_come_out(client, admin_token):
    resp = client.put(
        "/gateway/providers",
        json={
            "provider": "campay",
            "mode": "sandbox",
            "credentials": {"app_username": "u", "app_password": "sup3rs3cret"},
            "webhook_secret": "whsec",
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "sup3rs3cret" not in json.dumps(body)
    assert "whsec" not in json.dumps(body)
    # It reports *which* fields are set, never their values.
    assert set(body["configured_fields"]) == {"app_username", "app_password"}
    assert body["webhook_secret_set"] is True

    listed = client.get("/gateway/providers", headers=auth_header(admin_token))
    assert "sup3rs3cret" not in listed.text


def test_incomplete_credentials_are_rejected_at_save_time(client, admin_token):
    """Better a 422 in Settings than a failure the first time a customer pays."""
    resp = client.put(
        "/gateway/providers",
        json={"provider": "fapshi", "credentials": {"apiuser": "u"}, "activate": True},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422
    assert "apikey" in resp.json()["detail"]


def test_only_one_provider_is_active_at_a_time(client, admin_token):
    for provider, creds in (
        ("fake", {}),
        ("fapshi", {"apiuser": "u", "apikey": "k"}),
    ):
        client.put(
            "/gateway/providers",
            json={"provider": provider, "credentials": creds},
            headers=auth_header(admin_token),
        ).raise_for_status()

    client.post("/gateway/providers/fapshi/activate", headers=auth_header(admin_token)).raise_for_status()
    active = [
        p for p in client.get("/gateway/providers", headers=auth_header(admin_token)).json()
        if p["is_active"]
    ]
    assert [p["provider"] for p in active] == ["fapshi"]

    client.post("/gateway/providers/fake/activate", headers=auth_header(admin_token)).raise_for_status()
    active = [
        p for p in client.get("/gateway/providers", headers=auth_header(admin_token)).json()
        if p["is_active"]
    ]
    assert [p["provider"] for p in active] == ["fake"]


def test_catalog_describes_each_provider(client, admin_token):
    entries = client.get(
        "/gateway/providers/catalog", headers=auth_header(admin_token)
    ).json()
    by_name = {e["provider"]: e for e in entries}
    assert by_name["campay"]["required_fields"] == ["app_username", "app_password"]
    assert "payout_apiuser" in by_name["fapshi"]["optional_fields"]
    # MTN cannot authenticate callbacks; the UI needs to know that.
    assert by_name["mtn_momo"]["supports_webhook_verification"] is False


# --- Collections ----------------------------------------------------------
def test_collection_defaults_to_the_outstanding_balance(client, admin_token, gateway):
    invoice = gateway(outstanding=4200)
    resp = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677123456")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Charging the grand total of a partly-paid invoice is how you take money
    # twice, so the default is what is still owed.
    assert body["amount"] == 4200
    assert body["status"] == "pending"
    assert body["counterparty_msisdn"] == "237677123456"


def test_confirmed_payment_posts_to_the_ledger(client, admin_token, gateway, fake_erpnext):
    invoice = gateway(outstanding=5000)
    intent = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677123456").json()

    settled = refresh(client, admin_token, intent["id"]).json()
    assert settled["status"] == "succeeded"
    assert settled["reconciliation"] == "posted"
    assert settled["erpnext_payment_entry"], "a Payment Entry should have been created"

    entry = fake_erpnext.store[settled["erpnext_payment_entry"]]
    assert entry["doctype"] == "Payment Entry"
    assert entry["docstatus"] == 1, "the Payment Entry must be submitted, not draft"
    assert entry["references"][0]["reference_name"] == invoice


def test_posting_is_idempotent(client, admin_token, gateway):
    """Refreshing a settled payment repeatedly must not post it twice."""
    invoice = gateway()
    intent = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677123456").json()

    first = refresh(client, admin_token, intent["id"]).json()
    second = refresh(client, admin_token, intent["id"]).json()
    third = refresh(client, admin_token, intent["id"]).json()
    assert first["erpnext_payment_entry"] == second["erpnext_payment_entry"] == third["erpnext_payment_entry"]
    assert third["reconciliation"] == "posted"


def test_a_second_request_reuses_the_in_flight_attempt(client, admin_token, gateway):
    """A double click must produce one prompt, not two debits."""
    invoice = gateway()
    first = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677009999").json()
    second = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677009999").json()
    assert first["id"] == second["id"]


def test_force_allows_a_genuine_instalment(client, admin_token, gateway):
    """Paying an invoice in parts is normal here, so the guard is overridable."""
    invoice = gateway()
    first = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677009999").json()
    second = collect(
        client, admin_token, invoice_id=invoice, payer_msisdn="677009999",
        amount=1000, force=True,
    ).json()
    assert first["id"] != second["id"]


def test_failed_payment_is_never_posted(client, admin_token, gateway):
    invoice = gateway()
    intent = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677000000").json()
    settled = refresh(client, admin_token, intent["id"]).json()
    assert settled["status"] == "failed"
    assert settled["reconciliation"] == "pending"
    assert settled["erpnext_payment_entry"] == ""


def test_unconfirmed_payment_stays_pending(client, admin_token, gateway):
    """The payer never approved. Nothing should reach the ledger."""
    invoice = gateway()
    intent = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677009999").json()
    settled = refresh(client, admin_token, intent["id"]).json()
    assert settled["status"] == "pending"
    assert settled["erpnext_payment_entry"] == ""


def test_amount_mismatch_goes_to_review_instead_of_the_ledger(client, admin_token, gateway):
    """The money is real but the posting is not obvious — that is a human's
    decision, not a rounding one."""
    invoice = gateway(outstanding=5000)
    intent = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677001111").json()
    settled = refresh(client, admin_token, intent["id"]).json()
    assert settled["status"] == "succeeded"
    assert settled["reconciliation"] == "needs_review"
    assert "requested" in settled["review_reason"]
    assert settled["erpnext_payment_entry"] == ""


def test_collection_without_a_number_requires_a_link(client, admin_token, gateway):
    invoice = gateway()
    resp = collect(client, admin_token, invoice_id=invoice)
    assert resp.status_code == 422
    assert "phone number" in resp.json()["detail"]

    ok = collect(client, admin_token, invoice_id=invoice, hosted=True)
    assert ok.status_code == 201
    assert ok.json()["payment_url"]


def test_unsubmitted_invoice_cannot_be_collected(client, admin_token, fake_erpnext, gateway):
    fake_erpnext.store["SI-DRAFT"] = {
        "name": "SI-DRAFT", "doctype": "Sales Invoice", "docstatus": 0,
        "outstanding_amount": 1000, "customer": "Acme",
    }
    resp = collect(client, admin_token, invoice_id="SI-DRAFT", payer_msisdn="677123456")
    assert resp.status_code == 409
    assert "not submitted" in resp.json()["detail"]


def test_settled_invoice_has_nothing_to_collect(client, admin_token, gateway):
    invoice = gateway(outstanding=0)
    resp = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677123456")
    assert resp.status_code == 422


def test_provider_outage_surfaces_as_a_gateway_error(client, admin_token, gateway):
    invoice = gateway()
    resp = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677002222")
    assert resp.status_code == 502


def test_collecting_without_an_active_provider_is_refused(client, admin_token, fake_erpnext):
    client.post(
        "/gateway/providers/deactivate", headers=auth_header(admin_token)
    ).raise_for_status()
    resp = collect(client, admin_token, invoice_id="SI-NONE", payer_msisdn="677123456")
    assert resp.status_code == 409
    assert "No mobile-money provider is active" in resp.json()["detail"]


# --- Payouts --------------------------------------------------------------
def test_payout_settles_a_supplier_bill(client, admin_token, gateway, fake_erpnext):
    bill = gateway(outstanding=8000, doctype="Purchase Invoice")
    resp = client.post(
        "/gateway/payouts",
        json={"bill_id": bill, "payee_msisdn": "677123456"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    intent = resp.json()
    assert intent["direction"] == "payout"
    assert intent["amount"] == 8000

    settled = refresh(client, admin_token, intent["id"]).json()
    assert settled["status"] == "succeeded"
    assert settled["reconciliation"] == "posted"
    entry = fake_erpnext.store[settled["erpnext_payment_entry"]]
    assert entry["payment_type"] == "Pay"


def test_payout_requires_a_payee_number(client, admin_token, gateway):
    bill = gateway(doctype="Purchase Invoice")
    resp = client.post(
        "/gateway/payouts", json={"bill_id": bill, "payee_msisdn": ""},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422


# --- Webhooks -------------------------------------------------------------
def post_webhook(client, body: dict, headers: dict | None = None):
    return client.post(
        "/webhooks/payments/fake", json=body, headers=headers or {}
    )


def test_webhook_triggers_confirmation_and_posting(client, admin_token, gateway):
    invoice = gateway()
    intent = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677123456").json()

    resp = post_webhook(client, {"provider_ref": intent["provider_ref"], "status": "SUCCESSFUL"})
    assert resp.status_code == 200

    after = client.get(
        f"/gateway/payments/{intent['id']}", headers=auth_header(admin_token)
    ).json()
    assert after["status"] == "succeeded"
    assert after["reconciliation"] == "posted"


def test_a_lying_webhook_cannot_mark_an_invoice_paid(client, admin_token, gateway):
    """The load-bearing test of this module.

    The callback claims SUCCESSFUL for a payment the payer never approved. We
    re-ask the provider, which says PENDING, so nothing is posted. This is what
    makes an unauthenticated provider safe to enable.
    """
    invoice = gateway()
    intent = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677009999").json()

    post_webhook(client, {"provider_ref": intent["provider_ref"], "status": "SUCCESSFUL"})

    after = client.get(
        f"/gateway/payments/{intent['id']}", headers=auth_header(admin_token)
    ).json()
    assert after["status"] == "pending"
    assert after["reconciliation"] == "pending"
    assert after["erpnext_payment_entry"] == ""


def test_duplicate_webhook_delivery_is_a_no_op(client, admin_token, gateway, fake_erpnext):
    invoice = gateway()
    intent = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677123456").json()
    payload = {"provider_ref": intent["provider_ref"], "status": "SUCCESSFUL"}

    for _ in range(4):
        assert post_webhook(client, payload).status_code == 200

    after = client.get(
        f"/gateway/payments/{intent['id']}", headers=auth_header(admin_token)
    ).json()
    assert after["reconciliation"] == "posted"
    entries = [d for d in fake_erpnext.store.values() if d.get("doctype") == "Payment Entry"]
    matching = [
        e for e in entries
        if e.get("references", [{}])[0].get("reference_name") == invoice
    ]
    assert len(matching) == 1, "a retried callback must not post twice"


def test_webhook_for_an_unknown_reference_is_accepted_quietly(client):
    """Answer 200 regardless: a non-2xx makes providers retry forever, and the
    body must not tell a prober which references exist."""
    resp = post_webhook(client, {"provider_ref": "nope-does-not-exist", "status": "SUCCESSFUL"})
    assert resp.status_code == 200
    assert resp.json() == {"received": True}


def test_malformed_webhook_body_is_accepted_quietly(client):
    resp = client.post(
        "/webhooks/payments/fake",
        content=b"<<<not json>>>",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200


def test_webhook_for_an_unconfigured_provider_is_ignored(client):
    resp = client.post("/webhooks/payments/mtn_momo", json={"referenceId": "x"})
    assert resp.status_code == 200


# --- Sweep and manual intervention ---------------------------------------
def test_sweep_settles_and_posts_what_callbacks_missed(client, admin_token, gateway):
    """Callbacks that never arrive are routine, not exceptional."""
    invoices = [gateway() for _ in range(3)]
    for invoice in invoices:
        collect(client, admin_token, invoice_id=invoice, payer_msisdn="677123456").raise_for_status()

    result = client.post("/gateway/sweep", headers=auth_header(admin_token)).json()
    assert result["checked"] >= 3
    assert result["settled"] >= 3

    posted = client.get(
        "/gateway/payments", params={"reconciliation": "posted"},
        headers=auth_header(admin_token),
    ).json()
    assert len({p["erpnext_docname"] for p in posted} & set(invoices)) == 3


def test_review_can_be_resolved_and_reposted(client, admin_token, gateway):
    invoice = gateway(outstanding=5000)
    intent = collect(client, admin_token, invoice_id=invoice, payer_msisdn="677001111").json()
    flagged = refresh(client, admin_token, intent["id"]).json()
    assert flagged["reconciliation"] == "needs_review"

    resolved = client.post(
        f"/gateway/payments/{intent['id']}/retry-posting", headers=auth_header(admin_token)
    ).json()
    assert resolved["reconciliation"] == "posted"
    assert resolved["erpnext_payment_entry"]


def test_orphan_payment_can_be_attached_to_an_invoice(client, admin_token, gateway):
    """Someone paid with no reference; a human works out which invoice it was."""
    invoice = gateway()
    intent = collect(client, admin_token, payer_msisdn="677123456", amount=5000).json()
    assert intent["erpnext_docname"] == ""

    settled = refresh(client, admin_token, intent["id"]).json()
    assert settled["status"] == "succeeded"
    assert settled["reconciliation"] == "not_applicable"

    attached = client.post(
        f"/gateway/payments/{intent['id']}/attach",
        params={"doctype": "Sales Invoice", "docname": invoice},
        headers=auth_header(admin_token),
    ).json()
    assert attached["reconciliation"] == "posted"
    assert attached["erpnext_docname"] == invoice


# --- Access control -------------------------------------------------------
def test_sales_can_watch_a_payment_but_not_start_one(client, admin_token, gateway, make_token):
    invoice = gateway()
    sales = make_token("Sales")

    assert client.get("/gateway/payments", headers=auth_header(sales)).status_code == 200
    blocked = collect(client, sales, invoice_id=invoice, payer_msisdn="677123456")
    assert blocked.status_code == 403


def test_only_managers_touch_provider_credentials(client, make_token):
    accountant = make_token("Accountant")
    assert client.get("/gateway/providers", headers=auth_header(accountant)).status_code == 403
    resp = client.put(
        "/gateway/providers",
        json={"provider": "fake", "credentials": {}},
        headers=auth_header(accountant),
    )
    assert resp.status_code == 403


def test_gateway_requires_authentication(client):
    assert client.get("/gateway/payments").status_code == 401
    assert client.post("/gateway/collections", json={}).status_code == 401
