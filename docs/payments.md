# Mobile money — collections, payouts and reconciliation

How EquiMed asks a customer to pay an invoice over MTN MoMo or Orange Money,
settles a supplier bill, and gets both into the ledger without double-posting.

- [The rule that shapes everything](#the-rule-that-shapes-everything)
- [How it fits together](#how-it-fits-together)
- [Confirm before posting](#confirm-before-posting)
- [Two state axes](#two-state-axes)
- [Idempotency, in three layers](#idempotency-in-three-layers)
- [Providers](#providers)
- [Configuring a tenant](#configuring-a-tenant)
- [Webhooks](#webhooks)
- [Reconciliation and the sweep](#reconciliation-and-the-sweep)
- [Testing without credentials](#testing-without-credentials)
- [Endpoints](#endpoints)
- [Not done yet](#not-done-yet)
- [Before going live](#before-going-live)

---

## The rule that shapes everything

**The tenant owns the merchant account. We never hold their money.**

Each customer supplies credentials for *their own* CamPay / Fapshi / MTN
merchant account. Funds settle directly to them. EquiMed orchestrates and
reconciles; it is never in the flow of funds.

This is not a preference. The moment customer money passes through an account we
control, we are carrying float and performing money transmission, which is a
licensed activity under CEMAC banking regulation supervised by COBAC. That is a
different company with different capital requirements — not a feature.

Two consequences worth stating plainly:

* **Credentials are per tenant**, sealed at rest with Fernet
  (`utils/crypto.py`), and never returned by any API. The settings UI reports
  *which* fields are configured, never their values.
* **We cannot take a percentage of volume.** Not being in the flow means there
  is nothing to take a cut of. Realistic monetisation is a metered per-
  transaction SaaS fee — charging for the reconciliation, not the payment — or a
  referral arrangement with an aggregator. This corrects the "% of volume" note
  in [integrations.md](integrations.md).

---

## How it fits together

```
  POST /gateway/collections                    provider (CamPay/Fapshi/MTN)
        │                                                  │
        ▼                                                  │
  PaymentIntent (created)  ──── provider.collect() ───────▶│
        │                        returns pending           │
        │                                                  ▼
        │                                          customer's handset
        │                                                  │
        │        ┌───── webhook (a hint, never trusted) ◀───┘
        ▼        ▼
  PaymentGatewayService.refresh()
        │
        ├── provider.get_status()  ← the only authority on "did it pay?"
        │
        ├── amount matches?  no ──▶ reconciliation = needs_review  (stop)
        │                    yes
        ▼
  PaymentRepository.record()  ──▶  ERPNext Payment Entry (submitted)
        │
        ▼
  reconciliation = posted → appears in the bank book and aged receivables
```

Code map:

| Concern | Location |
| --- | --- |
| Provider contract, DTOs, phone normalisation | `integrations/payments/base.py` |
| Provider implementations | `integrations/payments/{campay,fapshi,mtn_momo,fake}.py` |
| Registry + credential field map | `integrations/payments/__init__.py` |
| Orchestration + reconciliation | `services/payment_gateway_service.py` |
| Credential management | `services/integration_service.py` |
| Durable state | `models/{integration,payment_intent,webhook_event}.py` |
| Routes | `api/gateway.py`, `api/webhooks.py` |

Adding a provider is one module in `integrations/payments/` plus a registry
entry. Nothing above it changes.

---

## Confirm before posting

**A webhook never moves money in the ledger.** It tells us *which* transaction
to go and ask about; the provider's status endpoint is the only thing allowed to
say "paid".

That discipline is why an unauthenticated provider is safe to enable at all. MTN
signs nothing — a forged callback claiming `SUCCESSFUL` is trivially
constructible — and it still cannot mark an invoice paid, because we re-ask MTN
and MTN says pending. `parse_webhook()` therefore returns only enough to
identify the transaction, and deliberately **does not carry an amount**:
accepting an amount from an unauthenticated callback is how you get charged for
someone else's payment.

The test that pins this is
`tests/test_payment_gateway.py::test_a_lying_webhook_cannot_mark_an_invoice_paid`.
Treat a failure there as a security incident.

---

## Two state axes

Kept separate on purpose:

| | Values | Question it answers |
| --- | --- | --- |
| `status` | `created → pending → succeeded / failed / expired` | Did the money move? |
| `reconciliation` | `pending → posted / needs_review / not_applicable` | Did we book it? |

Collapsing them would either lose a real payment or double-post one. A payment
can succeed while posting fails — ERPNext is down, the invoice was closed
meanwhile, the amount does not match. When that happens the row honestly says
"money arrived, ledger entry still owed", and the sweep retries.

**Amount mismatch is a review, not a guess.** If the provider settles a
different amount than we asked for, the money is real but the correct posting is
a judgement call, so it goes to a human rather than being approximated.

---

## Idempotency, in three layers

Because every one of these happens in normal operation, not just in failures:

1. **Business level** — requesting payment for an invoice that already has an
   attempt in flight returns the existing intent instead of prompting twice.
   A double-clicked button produces one prompt. `force: true` overrides it for
   genuine instalments, which are normal here.
2. **Callback level** — `webhook_event` has a unique
   `(tenant_id, provider, event_key)`. A retried delivery is recorded once and
   ignored thereafter. Providers retry; that is routine.
3. **Provider level** — our `reference` is sent as the provider's external id.
   For MTN the transaction UUID is *derived* from it
   (`uuid5(NAMESPACE_URL, ...)`), so replaying a request reuses the same
   `X-Reference-Id` and MTN's 409 is treated as "already accepted".

Posting itself is idempotent too: `_reconcile()` is a no-op once
`reconciliation` is `posted`.

---

## Providers

All endpoints below were taken from each provider's own documentation or
official SDK, not from memory.

### CamPay — `campay`

Aggregator covering MTN and Orange. Verified against
[their Python SDK](https://github.com/CamPay/campay-python-sdk).

```
POST /api/token/               {username, password} -> {token}
POST /api/collect/             Authorization: Token <token>
POST /api/withdraw/            payout
POST /api/get_payment_link/    hosted checkout
GET  /api/transaction/{ref}/   status: PENDING | SUCCESSFUL | FAILED
GET  /api/balance/
```

Hosts: `https://demo.campay.net` (sandbox) · `https://www.campay.net` (live).
Credentials: `app_username`, `app_password`.

> Two deliberate departures from their SDK: we keep **TLS verification on**
> (theirs passes `verify=False` on every call, which accepts any certificate on
> a channel carrying payment instructions), and we **cache the token** instead
> of refetching it before each request.

### Fapshi — `fapshi`

```
POST /initiate-pay          hosted link (expires after 24h)
POST /direct-pay            handset prompt; never expires
GET  /payment-status/{id}   CREATED | PENDING | SUCCESSFUL | FAILED | EXPIRED
POST /expire-pay
POST /payout
GET  /balance
```

Hosts: `https://sandbox.fapshi.com` · `https://live.fapshi.com`.
Auth: `apiuser` and `apikey` **headers** (not a bearer token).
Minimum 100 XAF. Status polling is capped at 6 requests/minute per transaction.

> **Collections and payouts need separate services.** Fapshi disables collection
> on a service once payouts are enabled for it, so a tenant doing both stores
> `payout_apiuser` / `payout_apikey` alongside the collection pair. They fall
> back to the collection pair when absent.

### MTN MoMo — `mtn_momo`

Direct integration. Worth it once volume makes the aggregator spread material.

```
POST /collection/token/                    Basic auth -> bearer
POST /collection/v1_0/requesttopay         202 Accepted, empty body
GET  /collection/v1_0/requesttopay/{ref}
POST /disbursement/token/
POST /disbursement/v1_0/transfer
GET  /disbursement/v1_0/transfer/{ref}
```

Hosts: `https://sandbox.momodeveloper.mtn.com` ·
`https://proxy.momoapi.mtn.com`.
Credentials: `api_user`, `api_key`, `collection_subscription_key`,
optionally `disbursement_subscription_key` and `target_environment`
(`mtncameroon` in production).

Collections and disbursements are **separate products** with separate
subscription keys and separate tokens.

### Fake — `fake`

The default. Behaviour is driven by the payer's number so failure paths can be
walked from the UI without editing code:

| Number ends in | Behaviour |
| --- | --- |
| `0000` | fails on first status check |
| `9999` | never leaves pending (payer walked away) |
| `1111` | succeeds for a *different amount* than requested |
| `2222` | provider outage (`ProviderUnavailable`) |
| anything else | pending, then succeeds |

State is process-wide, not per-instance — a provider is rebuilt on every
request, so instance state would vanish between initiating and confirming.

---

## Configuring a tenant

1. **Settings → provider credentials** (`PUT /gateway/providers`). Credentials
   are validated at save time: a set that cannot construct a provider is a 422
   now rather than a failure the first time a customer tries to pay.
2. **Activate one** (`POST /gateway/providers/{provider}/activate`). Exactly one
   provider is active per tenant — two would make it ambiguous which merchant
   account a collection lands in.
3. **Set the webhook URL** in the provider's dashboard (below).
4. Optionally set `settings.mode_of_payment` to the ERPNext Mode of Payment the
   receipts should post through (default `Mobile Money`). That is what routes
   the money to the right ledger account.

Gated on the `mobile_money` plan feature. Self-hosted installs have it
automatically (`tenancy/resolver.py::SELF_HOSTED_FEATURES`).

---

## Webhooks

```
https://<tenant-host>/api/webhooks/payments/<provider>
```

Per-tenant by hostname — the URL goes through `TenantMiddleware`, so an unknown
host is refused before any handler runs.

| Provider | Authentication |
| --- | --- |
| Fapshi | `x-wh-secret` header, compared in constant time |
| CamPay | signed payload; scheme documented only in their dashboard — treated as unverified |
| MTN | none whatsoever |

Since none of that is dependable, **the endpoint always re-confirms via the
status API**. It also always answers `200 {"received": true}`: providers retry
on any non-2xx, and the body must not tell a prober which references exist.

A suspended tenant's callbacks are rejected upstream by the middleware, which is
intentional — their ledger should not be written to. The payment is not lost;
the provider stays authoritative and the sweep picks it up on restore.

---

## Reconciliation and the sweep

`POST /gateway/sweep` polls every in-flight intent and retries every unposted
one. **Callbacks that never arrive are routine, not exceptional**, so this is
the backstop rather than a repair tool. It is safe to run on a schedule and safe
to run concurrently with callbacks.

When a payment cannot be posted automatically:

* `needs_review` with a reason on the intent,
* `POST /gateway/payments/{id}/retry-posting` once a human has fixed the cause,
* `POST /gateway/payments/{id}/attach` to point an orphaned payment (paid with
  no reference, or the wrong one) at the invoice it belongs to.

---

## Testing without credentials

Nothing here has been run against a live provider — there are no keys yet. What
exists instead:

* **Contract tests** (`tests/test_payment_providers.py`, 43 tests) intercept
  HTTP with `httpx.MockTransport` and assert the exact URL, headers and body we
  send against each provider's documented shape, plus how we map every status
  value. If a provider changes its API, or someone "tidies" a payload field,
  these fail.
* **Orchestration tests** (`tests/test_payment_gateway.py`, 31 tests) drive the
  whole loop against the fake provider and a fake ERPNext: posting, double-click
  protection, duplicate callbacks, lying callbacks, amount mismatch, outages,
  payouts, sweep, manual attach, and RBAC.

The bugs that cost money live in the orchestration, not in the HTTP call — which
is why the fake carries as much weight as the contract tests.

---

## Endpoints

| Method | Path | Access |
| --- | --- | --- |
| GET | `/gateway/providers/catalog` | Manager |
| GET | `/gateway/providers` | Manager |
| PUT | `/gateway/providers` | Manager |
| POST | `/gateway/providers/{provider}/activate` | Manager |
| POST | `/gateway/providers/deactivate` | Manager |
| DELETE | `/gateway/providers/{provider}` | Manager |
| POST | `/gateway/collections` | Manager, Accountant |
| POST | `/gateway/payouts` | Manager, Accountant |
| GET | `/gateway/payments` | Manager, Accountant, Sales |
| GET | `/gateway/payments/{id}?refresh=` | Manager, Accountant, Sales |
| POST | `/gateway/sweep` | Manager, Accountant |
| POST | `/gateway/payments/{id}/retry-posting` | Manager, Accountant |
| POST | `/gateway/payments/{id}/attach` | Manager, Accountant |
| POST | `/webhooks/payments/{provider}` | public (tenant-scoped by host) |

Administrator is always allowed. All routes also require the `mobile_money`
plan feature (402 otherwise).

---

## Not done yet

Deliberately out of scope for this branch:

* **No live testing.** Every provider is implemented from documentation. Expect
  to fix small things on first contact — field casing, an undocumented required
  parameter, CamPay's actual webhook signature scheme.
* **No frontend.** The API is complete; there is no Settings screen or "Request
  payment" button on an invoice yet.
* **No scheduled sweep.** `POST /gateway/sweep` exists but nothing calls it on a
  timer. Until something does, unposted payments wait for a manual sweep.
* **No usage metering**, so per-transaction billing is not possible yet — the
  gap flagged in [integrations.md](integrations.md#the-blocker-no-usage-metering).
* **No refunds.** Mobile-money reversals are usually a manual payout rather than
  an API reversal.
* **No partial-payment allocation UI.** Instalments work via `force: true` and
  an explicit amount, but nothing helps a user split an invoice.

---

## Before going live

- [ ] Set `SECRET_ENCRYPTION_KEY` explicitly. Left unset it is derived from
      `JWT_SECRET_KEY`, and rotating that would make every stored credential
      unreadable.
- [ ] Confirm CamPay's webhook signature scheme in their dashboard and tighten
      `CamPayProvider.parse_webhook` if it is verifiable.
- [ ] Run one real transaction per provider in sandbox, then one small live one.
- [ ] Confirm the ERPNext **Mode of Payment** exists and points at the right
      account, or receipts post to the default bank account.
- [ ] Schedule the sweep (cron hitting `/gateway/sweep`, or a worker).
- [ ] Decide who bears provider fees (merchant vs customer) and encode it in
      `settings`.
- [ ] Agree the settlement timing story: mobile money is typically T+1, so
      "paid" in the app is not "in the bank" the same day, and the bank book
      should represent that honestly.
