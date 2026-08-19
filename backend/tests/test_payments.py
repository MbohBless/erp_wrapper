"""RBAC for recording payments.

Money in and money out are guarded separately: a receipt is against a sales
invoice, which the Accountant raises; a payment settles a supplier bill, which
is a purchase operation and belongs to the Manager.
"""

from tests.conftest import auth_header


def test_accountant_receives_money_but_does_not_pay_suppliers(
    client, admin_token, make_token, fake_erpnext
):
    """Money out settles a supplier bill, which is a purchase operation — and
    purchases are the Manager's. Money in is against a sales invoice, which the
    Accountant raises."""
    token = make_token("Accountant")
    assert client.get("/payments", headers=auth_header(token)).status_code == 200
    assert client.post(
        "/payments/pay", json={"bill_id": "ANY"}, headers=auth_header(token)
    ).status_code == 403
    # Not 403: whatever it makes of the payload, the guard let them through.
    assert client.post(
        "/payments/receive", json={"invoice_id": "ANY"}, headers=auth_header(token)
    ).status_code != 403
