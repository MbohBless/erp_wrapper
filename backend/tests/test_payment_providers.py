"""Provider contract tests.

We have no live credentials, so these pin the wire format instead: every
assertion is about the exact URL, headers and body we send, and how we read the
responses each provider's documentation specifies. If a provider changes its
API, or someone "tidies" a payload field, these fail.

HTTP is intercepted with ``httpx.MockTransport`` — nothing leaves the machine.
"""

import contextlib
import json
from unittest.mock import patch

import httpx
import pytest

from integrations.payments import build_provider
from integrations.payments.base import (
    CollectionRequest,
    PaymentStatus,
    PayoutRequest,
    ProviderConfigError,
    ProviderUnavailable,
    local_msisdn,
    normalise_msisdn,
)
from integrations.payments.campay import CamPayProvider
from integrations.payments.fake import FakePaymentProvider
from integrations.payments.fapshi import FapshiProvider
from integrations.payments.mtn_momo import MtnMomoProvider


@contextlib.contextmanager
def mock_http(handler):
    """Route every httpx.AsyncClient through a MockTransport."""
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    with patch("httpx.AsyncClient", factory):
        yield


# --- Phone number normalisation ------------------------------------------
@pytest.mark.parametrize(
    "raw",
    ["+237 6 77 00 00 00", "677000000", "00237677000000", "237677000000", "237-677-000-000"],
)
def test_every_written_form_of_a_number_normalises_the_same(raw):
    """Paying the wrong person is unrecoverable, so this must not be loose."""
    assert normalise_msisdn(raw) == "237677000000"


def test_local_form_strips_the_country_code():
    assert local_msisdn("+237677000000") == "677000000"


def test_empty_number_stays_empty():
    assert normalise_msisdn("") == ""
    assert normalise_msisdn("   ") == ""


# --- Registry -------------------------------------------------------------
def test_unknown_provider_is_rejected():
    with pytest.raises(ProviderConfigError, match="Unknown payment provider"):
        build_provider("western_union", {})


def test_missing_credentials_are_named():
    with pytest.raises(ProviderConfigError, match="app_password"):
        build_provider("campay", {"app_username": "u"})


def test_fake_needs_no_credentials():
    assert build_provider("fake", {}).name == "fake"


# --- CamPay ---------------------------------------------------------------
CAMPAY_CREDS = {"app_username": "user", "app_password": "pass"}


@pytest.mark.asyncio
async def test_campay_collect_hits_the_documented_endpoints():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"token": "tok-123"})
        if request.url.path == "/api/collect/":
            return httpx.Response(
                200,
                json={
                    "reference": "bcedde9b-62a7-4421-96ac-2e6179552a1a",
                    "ussd_code": "*126#",
                    "operator": "MTN",
                },
            )
        return httpx.Response(404, json={"message": "no route"})

    provider = CamPayProvider(CAMPAY_CREDS, mode="sandbox")
    with mock_http(handler):
        intent = await provider.collect(
            CollectionRequest(
                reference="EQTEST1",
                amount=5000,
                payer_msisdn="677000000",
                description="Invoice SI-1",
            )
        )

    assert intent.provider_ref == "bcedde9b-62a7-4421-96ac-2e6179552a1a"
    # Initiation is never confirmation — the payer has not approved yet.
    assert intent.status is PaymentStatus.PENDING
    assert intent.ussd_code == "*126#"

    token_req, collect_req = seen
    assert str(token_req.url) == "https://demo.campay.net/api/token/"
    assert collect_req.headers["Authorization"] == "Token tok-123"
    body = json.loads(collect_req.content)
    assert body == {
        "amount": "5000",
        "currency": "XAF",
        "from": "237677000000",   # normalised to international form
        "description": "Invoice SI-1",
        "external_reference": "EQTEST1",
    }


@pytest.mark.asyncio
async def test_campay_uses_the_live_host_in_live_mode():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "www.campay.net"
        return httpx.Response(200, json={"token": "t"})

    provider = CamPayProvider(CAMPAY_CREDS, mode="live")
    with mock_http(handler):
        await provider._get_token()


@pytest.mark.asyncio
async def test_campay_caches_its_token():
    calls = {"token": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/token/":
            calls["token"] += 1
            return httpx.Response(200, json={"token": "tok"})
        return httpx.Response(200, json={"reference": "r", "status": "PENDING"})

    provider = CamPayProvider(CAMPAY_CREDS)
    with mock_http(handler):
        await provider.collect(CollectionRequest(reference="A", amount=100, payer_msisdn="677000000"))
        await provider.collect(CollectionRequest(reference="B", amount=100, payer_msisdn="677000000"))
    assert calls["token"] == 1, "token should be reused, not refetched per call"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("SUCCESSFUL", PaymentStatus.SUCCEEDED),
        ("FAILED", PaymentStatus.FAILED),
        ("PENDING", PaymentStatus.PENDING),
        ("SOMETHING_NEW", PaymentStatus.UNKNOWN),
    ],
)
@pytest.mark.asyncio
async def test_campay_status_mapping(raw, expected):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"token": "t"})
        return httpx.Response(
            200,
            json={
                "reference": "ref-1", "status": raw, "amount": 5000,
                "currency": "XAF", "operator": "MTN",
                "operator_reference": "1880106956",
            },
        )

    provider = CamPayProvider(CAMPAY_CREDS)
    with mock_http(handler):
        result = await provider.get_status("ref-1")
    assert result.status is expected
    assert result.operator_ref == "1880106956"


@pytest.mark.asyncio
async def test_campay_unopened_payment_link_is_unknown_not_failed():
    """A link nobody has opened has no transaction. Treating that as failure
    would cancel payments that are still perfectly alive."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/token/":
            return httpx.Response(200, json={"token": "t"})
        return httpx.Response(404, json={"message": "Transaction not found"})

    provider = CamPayProvider(CAMPAY_CREDS)
    with mock_http(handler):
        result = await provider.get_status("never-opened")
    assert result.status is PaymentStatus.UNKNOWN


@pytest.mark.asyncio
async def test_campay_server_error_is_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream down")

    provider = CamPayProvider(CAMPAY_CREDS)
    with mock_http(handler), pytest.raises(ProviderUnavailable):
        await provider._get_token()


# --- Fapshi ---------------------------------------------------------------
FAPSHI_CREDS = {"apiuser": "u", "apikey": "k"}


@pytest.mark.asyncio
async def test_fapshi_direct_pay_shape_and_auth_headers():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"message": "ok", "transId": "tx-1", "dateInitiated": "2026-08-03"}
        )

    provider = FapshiProvider(FAPSHI_CREDS, mode="sandbox")
    with mock_http(handler):
        intent = await provider.collect(
            CollectionRequest(
                reference="EQ2", amount=2500, payer_msisdn="+237677000000", payer_name="Ada"
            )
        )

    assert intent.provider_ref == "tx-1"
    request = seen[0]
    assert str(request.url) == "https://sandbox.fapshi.com/direct-pay"
    # Fapshi authenticates with two custom headers, not a bearer token.
    assert request.headers["apiuser"] == "u"
    assert request.headers["apikey"] == "k"
    body = json.loads(request.content)
    assert body["phone"] == "677000000"  # national form, per their docs
    assert body["externalId"] == "EQ2"
    assert body["amount"] == 2500


@pytest.mark.asyncio
async def test_fapshi_falls_back_to_a_link_when_there_is_no_number():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/initiate-pay"
        return httpx.Response(
            200, json={"transId": "tx-2", "link": "https://sandbox.fapshi.com/p/tx-2"}
        )

    provider = FapshiProvider(FAPSHI_CREDS)
    with mock_http(handler):
        intent = await provider.collect(CollectionRequest(reference="EQ3", amount=1000))
    assert intent.payment_url.endswith("/p/tx-2")


@pytest.mark.asyncio
async def test_fapshi_rejects_amounts_below_its_minimum():
    provider = FapshiProvider(FAPSHI_CREDS)
    with pytest.raises(Exception, match="at least 100"):
        await provider.collect(
            CollectionRequest(reference="EQ4", amount=50, payer_msisdn="677000000")
        )


@pytest.mark.asyncio
async def test_fapshi_payout_uses_the_separate_payout_service():
    """Fapshi disables collection on a service once payouts are enabled, so a
    tenant doing both holds two credential pairs."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"transId": "po-1"})

    provider = FapshiProvider(
        {**FAPSHI_CREDS, "payout_apiuser": "pu", "payout_apikey": "pk"}
    )
    with mock_http(handler):
        await provider.payout(
            PayoutRequest(reference="EQ5", amount=9000, payee_msisdn="677000000")
        )

    assert seen[0].url.path == "/payout"
    assert seen[0].headers["apiuser"] == "pu"
    assert seen[0].headers["apikey"] == "pk"


@pytest.mark.asyncio
async def test_fapshi_rate_limit_is_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "too many requests"})

    provider = FapshiProvider(FAPSHI_CREDS)
    with mock_http(handler), pytest.raises(ProviderUnavailable, match="rate limit"):
        await provider.get_status("tx-1")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("CREATED", PaymentStatus.PENDING),
        ("PENDING", PaymentStatus.PENDING),
        ("SUCCESSFUL", PaymentStatus.SUCCEEDED),
        ("FAILED", PaymentStatus.FAILED),
        ("EXPIRED", PaymentStatus.EXPIRED),
    ],
)
@pytest.mark.asyncio
async def test_fapshi_status_mapping(raw, expected):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"transId": "tx", "status": raw, "amount": 1000, "medium": "mobile money"},
        )

    provider = FapshiProvider(FAPSHI_CREDS)
    with mock_http(handler):
        assert (await provider.get_status("tx")).status is expected


def test_fapshi_verifies_its_webhook_secret():
    provider = FapshiProvider(FAPSHI_CREDS)
    body = json.dumps({"transId": "tx-9", "externalId": "EQ9", "status": "SUCCESSFUL"}).encode()

    good = provider.parse_webhook({"x-wh-secret": "s3cret"}, body, "s3cret")
    assert good.verified is True
    assert good.provider_ref == "tx-9"
    assert good.our_reference == "EQ9"

    # Wrong secret, and header casing variations, are all handled.
    assert provider.parse_webhook({"X-WH-Secret": "wrong"}, body, "s3cret").verified is False
    assert provider.parse_webhook({}, body, "s3cret").verified is False
    assert provider.parse_webhook({"X-WH-Secret": "s3cret"}, body, "s3cret").verified is True


def test_malformed_webhook_body_does_not_raise():
    """A provider posting rubbish must be recorded, not crash the endpoint."""
    provider = FapshiProvider(FAPSHI_CREDS)
    hint = provider.parse_webhook({}, b"not json at all", "s")
    assert hint.verified is False
    assert hint.event_key == ""


# --- MTN MoMo -------------------------------------------------------------
MTN_CREDS = {
    "api_user": "11111111-2222-3333-4444-555555555555",
    "api_key": "apikey",
    "collection_subscription_key": "subkey",
    "disbursement_subscription_key": "dsubkey",
}


@pytest.mark.asyncio
async def test_mtn_collect_sends_the_required_headers():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/token/"):
            return httpx.Response(200, json={"access_token": "bearer-1", "expires_in": 3600})
        return httpx.Response(202)  # MTN accepts with an empty body

    provider = MtnMomoProvider(MTN_CREDS, mode="sandbox")
    with mock_http(handler):
        intent = await provider.collect(
            CollectionRequest(reference="EQ6", amount=7000, payer_msisdn="677000000")
        )

    token_req, pay_req = seen
    assert token_req.url.path == "/collection/token/"
    assert token_req.headers["Authorization"].startswith("Basic ")
    assert token_req.headers["Ocp-Apim-Subscription-Key"] == "subkey"

    assert pay_req.url.path == "/collection/v1_0/requesttopay"
    assert pay_req.headers["Authorization"] == "Bearer bearer-1"
    assert pay_req.headers["X-Target-Environment"] == "sandbox"
    assert pay_req.headers["X-Reference-Id"] == intent.provider_ref
    body = json.loads(pay_req.content)
    assert body["payer"] == {"partyIdType": "MSISDN", "partyId": "237677000000"}
    assert body["externalId"] == "EQ6"


def test_mtn_transaction_id_is_deterministic():
    """The UUID is derived from our reference, so retrying the same logical
    payment reuses the same id and cannot double-charge."""
    first = MtnMomoProvider._transaction_id("EQ-SAME")
    second = MtnMomoProvider._transaction_id("EQ-SAME")
    assert first == second
    assert first != MtnMomoProvider._transaction_id("EQ-OTHER")


@pytest.mark.asyncio
async def test_mtn_conflict_on_replay_is_treated_as_accepted():
    """409 means MTN already has this X-Reference-Id — which is what a safe
    retry looks like, not an error."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token/"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(409, text="duplicate reference id")

    provider = MtnMomoProvider(MTN_CREDS)
    with mock_http(handler):
        intent = await provider.collect(
            CollectionRequest(reference="EQ7", amount=100, payer_msisdn="677000000")
        )
    assert intent.status is PaymentStatus.PENDING


@pytest.mark.asyncio
async def test_mtn_payout_uses_the_disbursement_product():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/token/"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(202)

    provider = MtnMomoProvider(MTN_CREDS)
    with mock_http(handler):
        await provider.payout(
            PayoutRequest(reference="EQ8", amount=100, payee_msisdn="677000000")
        )

    assert seen[0].url.path == "/disbursement/token/"
    assert seen[0].headers["Ocp-Apim-Subscription-Key"] == "dsubkey"
    assert seen[1].url.path == "/disbursement/v1_0/transfer"
    assert json.loads(seen[1].content)["payee"]["partyId"] == "237677000000"


@pytest.mark.asyncio
async def test_mtn_payout_without_a_disbursement_key_is_a_config_error():
    provider = MtnMomoProvider(
        {k: v for k, v in MTN_CREDS.items() if k != "disbursement_subscription_key"}
    )
    with pytest.raises(ProviderConfigError, match="disbursement"):
        await provider.payout(
            PayoutRequest(reference="EQ9", amount=100, payee_msisdn="677000000")
        )


def test_mtn_never_claims_a_verified_webhook():
    """MTN signs nothing, so a callback can never be trusted on its own."""
    provider = MtnMomoProvider(MTN_CREDS)
    assert provider.supports_webhook_verification is False
    hint = provider.parse_webhook(
        {"X-Reference-Id": "ref-1"},
        json.dumps({"externalId": "EQ10", "status": "SUCCESSFUL"}).encode(),
        "anything",
    )
    assert hint.verified is False
    assert hint.provider_ref == "ref-1"


# --- Fake -----------------------------------------------------------------
@pytest.mark.asyncio
async def test_fake_settles_by_default():
    FakePaymentProvider.reset()
    provider = FakePaymentProvider()
    intent = await provider.collect(
        CollectionRequest(reference="F1", amount=1000, payer_msisdn="677123456")
    )
    assert intent.status is PaymentStatus.PENDING
    assert (await provider.get_status(intent.provider_ref)).status is PaymentStatus.SUCCEEDED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "suffix,expected",
    [
        ("677000000", PaymentStatus.FAILED),     # ...0000
        ("677009999", PaymentStatus.PENDING),    # ...9999 — payer walked away
    ],
)
async def test_fake_magic_numbers_drive_failure_paths(suffix, expected):
    FakePaymentProvider.reset()
    provider = FakePaymentProvider()
    intent = await provider.collect(
        CollectionRequest(reference=f"F-{suffix}", amount=1000, payer_msisdn=suffix)
    )
    assert (await provider.get_status(intent.provider_ref)).status is expected


@pytest.mark.asyncio
async def test_fake_simulates_an_outage():
    FakePaymentProvider.reset()
    provider = FakePaymentProvider()
    with pytest.raises(ProviderUnavailable):
        await provider.collect(
            CollectionRequest(reference="F2", amount=1000, payer_msisdn="677002222")
        )


@pytest.mark.asyncio
async def test_fake_state_survives_reconstruction():
    """A provider is rebuilt per request, so its state must not live on the
    instance — otherwise every status check would return UNKNOWN."""
    FakePaymentProvider.reset()
    intent = await FakePaymentProvider().collect(
        CollectionRequest(reference="F3", amount=1000, payer_msisdn="677123456")
    )
    result = await FakePaymentProvider().get_status(intent.provider_ref)
    assert result.status is PaymentStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_fake_dedupes_on_reference_like_a_real_provider():
    FakePaymentProvider.reset()
    provider = FakePaymentProvider()
    request = CollectionRequest(reference="F4", amount=1000, payer_msisdn="677123456")
    first = await provider.collect(request)
    second = await provider.collect(request)
    assert first.provider_ref == second.provider_ref
