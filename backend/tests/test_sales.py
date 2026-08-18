"""Integration tests for the Sales module (invoices: list/create/view + RBAC)."""

from tests.conftest import auth_header

INVOICE = {
    "customer": "CHU Yaoundé",
    "items": [
        {"item_code": "THERMO-001", "qty": 2, "rate": 2500},
        {"item_code": "GLOVE-001", "qty": 10, "rate": 300},
    ],
}


def _create(client, token, **overrides):
    return client.post("/sales", json={**INVOICE, **overrides}, headers=auth_header(token))


def test_create_invoice_is_submitted(client, admin_token, fake_erpnext):
    resp = _create(client, admin_token)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["customer"] == "CHU Yaoundé"
    assert len(body["items"]) == 2
    assert body["items"][0]["amount"] == 5000  # 2 * 2500

    stored = fake_erpnext.store[body["id"]]
    assert stored["docstatus"] == 1  # posted to the ledger


def test_list_and_get_invoice(client, admin_token, fake_erpnext):
    created = _create(client, admin_token, customer="Hôpital Général Douala").json()

    listed = client.get("/sales", headers=auth_header(admin_token))
    assert listed.status_code == 200
    assert created["id"] in [i["id"] for i in listed.json()]

    got = client.get(f"/sales/{created['id']}", headers=auth_header(admin_token))
    assert got.status_code == 200
    assert got.json()["customer"] == "Hôpital Général Douala"


def test_search_by_customer(client, admin_token, fake_erpnext):
    _create(client, admin_token, customer="Pharmacie Centrale")
    _create(client, admin_token, customer="Clinique du Littoral")
    resp = client.get(
        "/sales", params={"search": "Pharmacie"}, headers=auth_header(admin_token)
    )
    assert {i["customer"] for i in resp.json()} == {"Pharmacie Centrale"}


def test_get_missing_invoice_404(client, admin_token, fake_erpnext):
    assert client.get("/sales/NOPE", headers=auth_header(admin_token)).status_code == 404


# --- RBAC ---


def test_sales_role_can_create(client, make_token, fake_erpnext):
    token = make_token("Sales")
    assert _create(client, token).status_code == 201


def test_accountant_can_view_but_not_create(client, admin_token, make_token, fake_erpnext):
    _create(client, admin_token)
    token = make_token("Accountant")
    assert client.get("/sales", headers=auth_header(token)).status_code == 200
    assert _create(client, token).status_code == 403


def test_store_keeper_cannot_view(client, make_token, fake_erpnext):
    token = make_token("Store Keeper")
    assert client.get("/sales", headers=auth_header(token)).status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/sales").status_code == 401


# --- Amending a posted invoice ------------------------------------------
#
# ERPNext cannot edit a submitted document. "Editing" an invoice is really
# cancel-then-amend: the original is reversed and a replacement posted under a
# new number. These assert on what reaches ERPNext, not on the response — a
# response can look right while the document behind it is wrong.

AMENDED = {
    "customer": "CHU Yaoundé",
    "items": [{"item_code": "THERMO-001", "qty": 3, "rate": 2600}],
    "remarks": "Quantity corrected after delivery note",
}


def _amend(client, token, invoice_id, **overrides):
    return client.put(
        f"/sales/{invoice_id}",
        json={**AMENDED, **overrides},
        headers=auth_header(token),
    )


def test_amend_cancels_the_original_and_posts_a_replacement(
    client, admin_token, fake_erpnext
):
    original = _create(client, admin_token).json()["id"]

    resp = _amend(client, admin_token, original)
    assert resp.status_code == 200, resp.text
    replacement = resp.json()["id"]

    # The invoice number changes. Callers must read it back rather than assume
    # they still hold the one they edited.
    assert replacement == f"{original}-1"

    assert fake_erpnext.store[original]["docstatus"] == 2  # reversed, not rewritten
    posted = fake_erpnext.store[replacement]
    assert posted["docstatus"] == 1
    assert posted["amended_from"] == original  # the trail back
    assert posted["items"] == [{"item_code": "THERMO-001", "qty": 3, "rate": 2600}]
    assert posted["remarks"] == "Quantity corrected after delivery note"


def test_amend_backdating_sets_posting_time(client, admin_token, fake_erpnext):
    original = _create(client, admin_token).json()["id"]
    new_id = _amend(client, admin_token, original, posting_date="2026-03-04").json()["id"]

    posted = fake_erpnext.store[new_id]
    assert posted["posting_date"] == "2026-03-04"
    # Without this ERPNext ignores posting_date and stamps today, silently
    # moving a correction into the wrong period.
    assert posted["set_posting_time"] == 1


def test_amend_refused_once_money_has_been_received(client, admin_token, fake_erpnext):
    original = _create(client, admin_token).json()["id"]
    fake_erpnext.store[original].update(grand_total=10000, outstanding_amount=4000)

    resp = _amend(client, admin_token, original)
    assert resp.status_code == 409
    assert "6,000 XAF received" in resp.json()["detail"]
    # The refusal has to come *before* the cancel: ERPNext would reject this
    # too, but only after the invoice had already been reversed.
    assert fake_erpnext.store[original]["docstatus"] == 1


def test_amend_refused_on_an_opening_balance(client, admin_token, fake_erpnext):
    original = _create(client, admin_token).json()["id"]
    fake_erpnext.store[original]["is_opening"] = "Yes"

    resp = _amend(client, admin_token, original)
    assert resp.status_code == 409
    assert "opening balance" in resp.json()["detail"]
    assert fake_erpnext.store[original]["docstatus"] == 1


def test_amend_resumes_a_cancel_that_lost_its_replacement(
    client, admin_token, fake_erpnext
):
    """The cancel and the re-post are two calls; the second can fail.

    That leaves the invoice cancelled with nothing standing in for it. Asking
    again must finish the job rather than refuse — and must not post a second
    replacement if the first one did land.
    """
    original = _create(client, admin_token).json()["id"]
    # The state a half-finished amend leaves behind, exactly as ERPNext does:
    # reversed, and with the outstanding amount zeroed.
    fake_erpnext.store[original].update(
        grand_total=10000, outstanding_amount=0, docstatus=2, status="Cancelled"
    )

    # Resumes: a cancelled invoice reads as fully settled, which must not be
    # mistaken for "someone paid this".
    first = _amend(client, admin_token, original)
    assert first.status_code == 200, first.text
    assert first.json()["id"] == f"{original}-1"

    # Asked again — e.g. the response was lost in transit — the same
    # replacement comes back instead of a second invoice for the same sale.
    second = _amend(client, admin_token, original)
    assert second.status_code == 200
    assert second.json()["id"] == f"{original}-1"
    assert f"{original}-2" not in fake_erpnext.store


def test_cancelled_invoices_are_not_listed(client, admin_token, fake_erpnext):
    original = _create(client, admin_token, customer="Clinique Bastos").json()["id"]
    replacement = _amend(
        client, admin_token, original, customer="Clinique Bastos"
    ).json()["id"]

    ids = [i["id"] for i in client.get("/sales", headers=auth_header(admin_token)).json()]
    assert replacement in ids
    assert original not in ids  # reversed: showing it would double the sale


def test_amend_reports_the_lineage(client, admin_token, fake_erpnext):
    original = _create(client, admin_token).json()["id"]
    new_id = _amend(client, admin_token, original).json()["id"]

    body = client.get(f"/sales/{new_id}", headers=auth_header(admin_token)).json()
    assert body["amended_from"] == original
    assert body["is_cancelled"] is False

    was = client.get(f"/sales/{original}", headers=auth_header(admin_token)).json()
    assert was["is_cancelled"] is True


def test_amend_carries_the_tax_template_and_stock_flag(
    client, admin_token, fake_erpnext
):
    """A PUT replaces the whole document, so what the read model hides, an edit
    clears. An invoice re-posted without its VAT template bills the wrong total;
    one re-posted without `update_stock` leaves the goods on hand after the
    cancel returned them. Both must survive the round trip, which means both
    must be readable in the first place.
    """
    created = _create(
        client, admin_token, update_stock=True, taxes_and_charges="VAT 19.25% - QBS"
    ).json()
    assert created["update_stock"] is True
    assert created["taxes_and_charges"] == "VAT 19.25% - QBS"

    new_id = _amend(
        client,
        admin_token,
        created["id"],
        update_stock=created["update_stock"],
        taxes_and_charges=created["taxes_and_charges"],
    ).json()["id"]

    posted = fake_erpnext.store[new_id]
    assert posted["update_stock"] == 1
    assert posted["taxes_and_charges"] == "VAT 19.25% - QBS"


def test_amend_missing_invoice_404(client, admin_token, fake_erpnext):
    assert _amend(client, admin_token, "NOPE").status_code == 404


def test_only_manager_and_administrator_may_amend(
    client, admin_token, make_token, fake_erpnext
):
    original = _create(client, admin_token).json()["id"]

    # Sales may raise an invoice but not unwind a posted one.
    assert _amend(client, make_token("Sales"), original).status_code == 403
    assert _amend(client, make_token("Accountant"), original).status_code == 403
    assert _amend(client, make_token("Store Keeper"), original).status_code == 403
    assert fake_erpnext.store[original]["docstatus"] == 1

    assert _amend(client, make_token("Manager"), original).status_code == 200
