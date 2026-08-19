"""Integration tests for the Inventory module (warehouses, batches, stock,
goods received/issued) + RBAC, against a fake ERPNext."""

from tests.conftest import auth_header


# ----------------------------------------------------------------- Warehouses
def test_warehouse_crud(client, admin_token, fake_erpnext):
    resp = client.post(
        "/inventory/warehouses",
        json={"name": "Main Store", "is_group": False},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["id"] == "Main Store"
    assert fake_erpnext.store["Main Store"]["warehouse_name"] == "Main Store"

    assert (
        client.get(
            "/inventory/warehouses/Main Store", headers=auth_header(admin_token)
        ).status_code
        == 200
    )
    upd = client.put(
        "/inventory/warehouses/Main Store",
        json={"disabled": True},
        headers=auth_header(admin_token),
    )
    assert upd.status_code == 200 and upd.json()["disabled"] is True

    assert (
        client.delete(
            "/inventory/warehouses/Main Store", headers=auth_header(admin_token)
        ).status_code
        == 204
    )
    assert (
        client.get(
            "/inventory/warehouses/Main Store", headers=auth_header(admin_token)
        ).status_code
        == 404
    )


# -------------------------------------------------------------------- Batches
def _batch_tracked_product(client, token, sku="THERMO-001"):
    """A batch needs a product that is actually batch-tracked.

    ERPNext refuses to create a Batch for an item without has_batch_no, so the
    service checks first. These tests previously posted a batch for a SKU that
    did not exist anywhere, which only passed because the fake accepted it.
    """
    client.post(
        "/products",
        json={"sku": sku, "name": f"Product {sku}", "track_batches": True},
        headers=auth_header(token),
    )
    return sku


def test_batch_create_with_expiry(client, admin_token, fake_erpnext):
    _batch_tracked_product(client, admin_token)
    resp = client.post(
        "/inventory/batches",
        json={
            "batch_id": "BATCH-001",
            "item_code": "THERMO-001",
            "expiry_date": "2027-01-31",
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == "BATCH-001"
    assert body["expiry_date"] == "2027-01-31"
    # Domain -> ERPNext field mapping.
    stored = fake_erpnext.store["BATCH-001"]
    assert stored["item"] == "THERMO-001"
    assert stored["expiry_date"] == "2027-01-31"

    got = client.get(
        "/inventory/batches/BATCH-001", headers=auth_header(admin_token)
    )
    assert got.status_code == 200
    assert got.json()["item_code"] == "THERMO-001"


def test_batch_duplicate_conflict(client, admin_token, fake_erpnext):
    _batch_tracked_product(client, admin_token)
    body = {"batch_id": "DUP-B", "item_code": "THERMO-001"}
    assert (
        client.post(
            "/inventory/batches", json=body, headers=auth_header(admin_token)
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/inventory/batches", json=body, headers=auth_header(admin_token)
        ).status_code
        == 409
    )


# ---------------------------------------------------------------- Stock levels
def test_stock_levels(client, admin_token, fake_erpnext):
    fake_erpnext.store["bin-1"] = {
        "item_code": "THERMO-001",
        "warehouse": "Main Store",
        "actual_qty": 25,
        "projected_qty": 25,
    }
    fake_erpnext.store["bin-2"] = {
        "item_code": "GLOVE-001",
        "warehouse": "Main Store",
        "actual_qty": 100,
    }
    resp = client.get("/inventory/stock", headers=auth_header(admin_token))
    assert resp.status_code == 200
    rows = {r["item_code"]: r for r in resp.json()}
    assert rows["THERMO-001"]["actual_qty"] == 25
    assert rows["GLOVE-001"]["warehouse"] == "Main Store"


# ------------------------------------------------------------ Goods movements
def _movement_setup(client, token, fake, warehouse="Main Store",
                    sku="THERMO-001", on_hand=0.0, track_batches=False):
    """Prerequisites a stock movement now validates before ERPNext sees it.

    These tests used to post a movement into a warehouse that existed nowhere,
    for an item that existed nowhere, and pass — because the fake accepts any
    document. Real ERPNext answers "Group node warehouse is not allowed" or
    "X is not a stock Item", which reached the user as an opaque 502.
    """
    client.post("/inventory/warehouses", json={"name": warehouse},
                headers=auth_header(token))
    # One create only: a second POST for the same SKU is a 409, so passing the
    # flag afterwards would silently not apply.
    client.post(
        "/products",
        json={"sku": sku, "name": f"Product {sku}", "track_batches": track_batches},
        headers=auth_header(token),
    )
    if on_hand:
        # ERPNext keeps one Bin per (item, warehouse); the fake has no stock
        # ledger, so state it directly.
        fake.store[f"BIN-{sku}-{warehouse}"] = {
            "doctype": "Bin", "name": f"BIN-{sku}-{warehouse}",
            "item_code": sku, "warehouse": warehouse, "actual_qty": on_hand,
        }


def test_goods_received(client, admin_token, fake_erpnext):
    _movement_setup(client, admin_token, fake_erpnext)
    resp = client.post(
        "/inventory/receive",
        json={
            "warehouse": "Main Store",
            "items": [
                {
                    "item_code": "THERMO-001",
                    "qty": 10,
                    "batch_no": "BATCH-001",
                    "rate": 1500,
                }
            ],
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["stock_entry_type"] == "Material Receipt"
    assert body["items"][0]["item_code"] == "THERMO-001"
    assert body["items"][0]["warehouse"] == "Main Store"

    stored = fake_erpnext.store[body["id"]]
    assert stored["docstatus"] == 1  # submitted
    assert stored["to_warehouse"] == "Main Store"
    assert stored["items"][0]["t_warehouse"] == "Main Store"
    assert stored["items"][0]["basic_rate"] == 1500


def test_goods_issued(client, admin_token, fake_erpnext):
    _movement_setup(client, admin_token, fake_erpnext, on_hand=50)
    resp = client.post(
        "/inventory/issue",
        json={
            "warehouse": "Main Store",
            "items": [{"item_code": "THERMO-001", "qty": 3}],
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["stock_entry_type"] == "Material Issue"
    stored = fake_erpnext.store[body["id"]]
    assert stored["docstatus"] == 1
    assert stored["from_warehouse"] == "Main Store"
    assert stored["items"][0]["s_warehouse"] == "Main Store"


def test_receive_requires_items(client, admin_token, fake_erpnext):
    resp = client.post(
        "/inventory/receive",
        json={"warehouse": "Main Store", "items": []},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422  # min_length=1


# ------------------------------------------------------------------- RBAC
def test_store_keeper_can_receive(client, admin_token, make_token, fake_erpnext):
    _movement_setup(client, admin_token, fake_erpnext)
    token = make_token("Store Keeper")
    resp = client.post(
        "/inventory/receive",
        json={
            "warehouse": "Main Store",
            "items": [{"item_code": "THERMO-001", "qty": 5}],
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201


def test_sales_can_view_stock_but_not_receive(client, make_token, fake_erpnext):
    token = make_token("Sales")
    assert client.get("/inventory/stock", headers=auth_header(token)).status_code == 200
    resp = client.post(
        "/inventory/receive",
        json={
            "warehouse": "Main Store",
            "items": [{"item_code": "THERMO-001", "qty": 5}],
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_accountant_cannot_manage_warehouse(client, make_token, fake_erpnext):
    token = make_token("Accountant")
    assert client.get(
        "/inventory/warehouses", headers=auth_header(token)
    ).status_code == 200
    resp = client.post(
        "/inventory/warehouses",
        json={"name": "Nope"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/inventory/stock").status_code == 401
    assert client.get("/inventory/warehouses").status_code == 401


def test_batch_for_unknown_sku_is_a_clear_404(client, admin_token, fake_erpnext):
    """Left to ERPNext this was a 500: "cannot unpack non-iterable NoneType"."""
    resp = client.post(
        "/inventory/batches",
        json={"batch_id": "B-UNKNOWN", "item_code": "NO-SUCH-SKU"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 404
    assert "NO-SUCH-SKU" in resp.json()["detail"]


def test_batch_for_untracked_product_explains_what_to_do(
    client, admin_token, fake_erpnext
):
    """ERPNext's own message is "The selected item cannot have Batch", which
    does not say that batch tracking is a per-product flag."""
    client.post(
        "/products",
        json={"sku": "PLAIN-001", "name": "Not batch tracked"},
        headers=auth_header(admin_token),
    )
    resp = client.post(
        "/inventory/batches",
        json={"batch_id": "B-PLAIN", "item_code": "PLAIN-001"},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422
    assert "batch-tracked" in resp.json()["detail"]


def test_track_batches_round_trips_to_has_batch_no(client, admin_token, fake_erpnext):
    created = client.post(
        "/products",
        json={"sku": "TRACKED-1", "name": "Tracked", "track_batches": True},
        headers=auth_header(admin_token),
    )
    assert created.status_code == 201, created.text
    assert fake_erpnext.store["TRACKED-1"]["has_batch_no"] == 1
    assert created.json()["track_batches"] is True


def test_receive_into_a_warehouse_group_is_refused_clearly(
    client, admin_token, fake_erpnext
):
    """ERPNext says "Group node warehouse is not allowed to select for
    transactions", which arrives as a 502 and never names the field."""
    client.post(
        "/inventory/warehouses",
        json={"name": "All Warehouses", "is_group": True},
        headers=auth_header(admin_token),
    )
    client.post("/products", json={"sku": "GRP-1", "name": "Item"},
                headers=auth_header(admin_token))
    resp = client.post(
        "/inventory/receive",
        json={"warehouse": "All Warehouses",
              "items": [{"item_code": "GRP-1", "qty": 1}]},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422
    assert "group" in resp.json()["detail"].lower()


def test_receiving_a_batch_tracked_item_needs_a_batch_number(
    client, admin_token, fake_erpnext
):
    _movement_setup(client, admin_token, fake_erpnext, sku="TRK-1",
                    track_batches=True)
    resp = client.post(
        "/inventory/receive",
        json={"warehouse": "Main Store",
              "items": [{"item_code": "TRK-1", "qty": 5}]},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422
    assert "batch" in resp.json()["detail"].lower()


def test_issuing_more_than_is_held_says_how_much_there_is(
    client, admin_token, fake_erpnext
):
    """Previously a raw pymysql DataError, or a bare negative-stock refusal."""
    _movement_setup(client, admin_token, fake_erpnext, sku="FEW-1", on_hand=4)
    resp = client.post(
        "/inventory/issue",
        json={"warehouse": "Main Store",
              "items": [{"item_code": "FEW-1", "qty": 10}]},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "4" in detail and "FEW-1" in detail


def test_receive_for_unknown_sku_is_a_clear_404(client, admin_token, fake_erpnext):
    _movement_setup(client, admin_token, fake_erpnext)
    resp = client.post(
        "/inventory/receive",
        json={"warehouse": "Main Store",
              "items": [{"item_code": "GHOST-1", "qty": 1}]},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 404
    assert "GHOST-1" in resp.json()["detail"]
