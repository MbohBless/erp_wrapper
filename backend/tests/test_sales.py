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


def test_accountant_conducts_sales_but_cannot_unwind_one(
    client, admin_token, make_token, fake_erpnext
):
    token = make_token("Accountant")
    assert client.get("/sales", headers=auth_header(token)).status_code == 200
    created = _create(client, token)
    assert created.status_code == 201, created.text
    # Amending cancels a posted invoice and re-posts it; that stays with Manager.
    assert _amend(client, token, created.json()["id"]).status_code == 403


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


def test_line_items_carry_the_item_name(client, admin_token, fake_erpnext):
    """The drawer showed a bare SKU, which nobody in the warehouse reads as a
    product. ERPNext stamps `item_name` onto each line when the invoice is
    saved, so it is the name the document was *billed* as."""
    created = _create(client, admin_token).json()
    for row in fake_erpnext.store[created["id"]]["items"]:
        row["item_name"] = "Digital Thermometer" if "THERMO" in row["item_code"] \
            else "Examination Gloves (M)"

    body = client.get(f"/sales/{created['id']}", headers=auth_header(admin_token)).json()
    assert [(i["item_code"], i["item_name"]) for i in body["items"]] == [
        ("THERMO-001", "Digital Thermometer"),
        ("GLOVE-001", "Examination Gloves (M)"),
    ]


def test_amend_does_not_send_a_stale_item_name(client, admin_token, fake_erpnext):
    """ERPNext fills `item_name` from the Item master on save. Echoing back the
    name the original was billed under would pin it, so a product renamed since
    would keep its old name on every correction."""
    original = _create(client, admin_token).json()["id"]
    new_id = _amend(client, admin_token, original).json()["id"]

    for row in fake_erpnext.store[new_id]["items"]:
        assert "item_name" not in row


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


# --- Commissioned sales --------------------------------------------------
#
# A sale brokered by an agent and billed below the product's own selling price.
# The customer pays the lower figure; nobody is owed a payout. What has to
# survive is the *reason*: without it, a deliberate concession and a mistyped
# rate are the same row.

PRODUCT = {
    "name": "Gazelle HB Variant Cartridges",
    "sku": "GHBC-0002",
    "selling_price": 87500,
    "unit": "Nos",
}


def _catalogue(client, token, **overrides):
    return client.post(
        "/products", json={**PRODUCT, **overrides}, headers=auth_header(token)
    )


def test_commissioned_sale_records_the_flag_and_the_agent(
    client, admin_token, fake_erpnext
):
    _catalogue(client, admin_token)
    resp = _create(
        client, admin_token,
        items=[{"item_code": "GHBC-0002", "qty": 2, "rate": 70000}],
        is_commissioned=True, commission_agent="Jean-Paul Nkeng",
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["is_commissioned"] is True
    assert body["commission_agent"] == "Jean-Paul Nkeng"

    stored = fake_erpnext.store[body["id"]]
    assert stored["custom_is_commissioned"] == 1
    assert stored["custom_commission_agent"] == "Jean-Paul Nkeng"


def test_the_line_carries_the_list_price_it_was_discounted_from(
    client, admin_token, fake_erpnext
):
    """`price_list_rate` is what makes the concession measurable. ERPNext fills
    it from the Standard Selling price list when it is absent — and items with
    no entry there record a list price of zero, which reads as no discount at
    all."""
    _catalogue(client, admin_token)
    body = _create(
        client, admin_token,
        items=[{"item_code": "GHBC-0002", "qty": 2, "rate": 70000}],
        is_commissioned=True, commission_agent="Jean-Paul Nkeng",
    ).json()

    row = fake_erpnext.store[body["id"]]["items"][0]
    assert row["price_list_rate"] == 87500  # the product's own selling price
    assert row["rate"] == 70000             # what was actually charged

    assert body["items"][0]["list_rate"] == 87500
    assert body["items"][0]["rate"] == 70000


def test_the_list_price_is_read_from_the_catalogue_not_the_request(
    client, admin_token, fake_erpnext
):
    """Otherwise the discount is self-declared: send a list price of 10,000,000
    and any sale looks like a heroic concession."""
    _catalogue(client, admin_token)
    body = _create(
        client, admin_token,
        items=[{"item_code": "GHBC-0002", "qty": 1, "rate": 70000,
                "list_rate": 10_000_000, "price_list_rate": 10_000_000}],
        is_commissioned=True, commission_agent="Jean-Paul Nkeng",
    ).json()
    assert fake_erpnext.store[body["id"]]["items"][0]["price_list_rate"] == 87500


def test_an_item_with_no_price_on_file_records_no_list_price(
    client, admin_token, fake_erpnext
):
    """A false zero would report the whole sale as given away."""
    _catalogue(client, admin_token, sku="NOPRICE-1", selling_price=None)
    body = _create(
        client, admin_token,
        items=[{"item_code": "NOPRICE-1", "qty": 1, "rate": 5000}],
    ).json()

    assert "price_list_rate" not in fake_erpnext.store[body["id"]]["items"][0]
    assert body["items"][0]["list_rate"] is None


def test_a_free_line_is_not_repriced_to_the_list_rate(
    client, admin_token, fake_erpnext
):
    """ERPNext recomputes `rate` from `price_list_rate` when the rate is falsy,
    so sending a list price against a giveaway line would bill for it."""
    _catalogue(client, admin_token)
    body = _create(
        client, admin_token,
        items=[{"item_code": "GHBC-0002", "qty": 1, "rate": 0}],
    ).json()
    assert "price_list_rate" not in fake_erpnext.store[body["id"]]["items"][0]


def test_a_commissioned_sale_must_name_its_agent(client, admin_token, fake_erpnext):
    _catalogue(client, admin_token)
    resp = _create(client, admin_token, is_commissioned=True)
    assert resp.status_code == 422
    assert "name of the agent" in resp.json()["detail"]

    resp = _create(client, admin_token, is_commissioned=True, commission_agent="   ")
    assert resp.status_code == 422


def test_an_agent_without_the_flag_is_refused(client, admin_token, fake_erpnext):
    """Otherwise the name sits on an invoice that no commission report finds."""
    resp = _create(client, admin_token, commission_agent="Jean-Paul Nkeng")
    assert resp.status_code == 422
    assert "not marked as a commissioned sale" in resp.json()["detail"]


def test_an_ordinary_sale_is_unaffected(client, admin_token, fake_erpnext):
    _catalogue(client, admin_token)
    body = _create(
        client, admin_token, items=[{"item_code": "GHBC-0002", "qty": 1, "rate": 87500}]
    ).json()
    assert body["is_commissioned"] is False
    assert body["commission_agent"] is None
    assert fake_erpnext.store[body["id"]].get("custom_is_commissioned") is None


def test_amending_keeps_the_sale_commissioned(client, admin_token, fake_erpnext):
    """A PUT replaces the whole document, so a correction that forgets these
    turns a tracked concession into an unexplained low price."""
    _catalogue(client, admin_token)
    original = _create(
        client, admin_token,
        items=[{"item_code": "GHBC-0002", "qty": 2, "rate": 70000}],
        is_commissioned=True, commission_agent="Jean-Paul Nkeng",
    ).json()["id"]

    amended = client.put(
        f"/sales/{original}",
        json={"customer": INVOICE["customer"],
              "items": [{"item_code": "GHBC-0002", "qty": 3, "rate": 70000}],
              "is_commissioned": True, "commission_agent": "Jean-Paul Nkeng"},
        headers=auth_header(admin_token),
    ).json()

    assert amended["is_commissioned"] is True
    assert amended["commission_agent"] == "Jean-Paul Nkeng"
    posted = fake_erpnext.store[amended["id"]]
    assert posted["custom_is_commissioned"] == 1
    assert posted["items"][0]["price_list_rate"] == 87500


# --- Paging --------------------------------------------------------------


def test_pages_cover_every_invoice_exactly_once(client, admin_token, fake_erpnext):
    """The list page asks for one row more than it shows, to learn whether there
    is another page. What must hold is that walking the pages yields every
    invoice and none of them twice."""
    made = {_create(client, admin_token, customer=f"Clinique {i}").json()["id"]
            for i in range(7)}

    size, seen, page = 3, [], 0
    # Bounded, not `while True`. A `start` that is ignored makes every page
    # identical, so an unbounded walk would hang instead of failing — and a
    # test that hangs on the bug it is meant to catch reports nothing at all.
    while page < 10:
        batch = client.get(
            "/sales", params={"limit": size + 1, "start": page * size},
            headers=auth_header(admin_token),
        ).json()
        seen.extend(i["id"] for i in batch[:size])
        if len(batch) <= size:
            break
        page += 1
    else:
        raise AssertionError("paging never reached the end — is `start` ignored?")

    assert len(seen) == len(set(seen)), "an invoice appeared on two pages"
    assert made <= set(seen), "an invoice never appeared on any page"


def test_the_probe_row_is_what_reveals_a_next_page(client, admin_token, fake_erpnext):
    for i in range(4):
        _create(client, admin_token, customer=f"Hopital {i}")

    def fetch(limit, start=0):
        return client.get("/sales", params={"limit": limit, "start": start},
                          headers=auth_header(admin_token)).json()

    # Four invoices, pages of three: the fourth row is the signal.
    assert len(fetch(4)) == 4          # asked for size+1, got it -> more exists
    assert len(fetch(4, start=3)) == 1  # last page returns fewer than asked
