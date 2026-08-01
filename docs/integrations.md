# Integrations & add-ons — research and roadmap

Candidate add-ons that can ship as **plan features**, and the sequencing between
them. Nothing here is implemented yet; this is the research that decides what to
build and in what order.

> **Researched August 2026.** Payment rails and — especially — tax rules move
> fast. Re-verify anything in the [Regulatory](#regulatory-e-invoicing-is-now-law)
> section against the DGI directly before acting on it. Sources are listed at the
> bottom with the caveats that apply to each.

- [Why this is cheap for us](#why-this-is-cheap-for-us)
- [Regulatory: e-invoicing is now law](#regulatory-e-invoicing-is-now-law)
- [The portfolio](#the-portfolio)
- [Mobile money collections](#mobile-money-collections)
- [WhatsApp delivery and dunning](#whatsapp-delivery-and-dunning)
- [Payroll](#payroll)
- [Bank statement import](#bank-statement-import)
- [Leverage, don't build](#leverage-dont-build)
- [The blocker: no usage metering](#the-blocker-no-usage-metering)
- [Recommended order](#recommended-order)
- [Sources](#sources)

---

## Why this is cheap for us

The multi-tenancy work already built the machinery every item below needs.
An add-on is a **feature flag plus a module**:

```python
# platform/api/models/plan.py — add the capability to the vocabulary
FEATURE_MOBILE_MONEY = "mobile_money"

# backend/api/<module>.py — gate the routes
has_mobile_money = require_feature("mobile_money")
```

Selling it is then a data change in the control plane, not a deploy. Plans
already carry a feature list, the tenant app already receives it through tenant
resolution, and `require_feature(...)` already returns **402** so a caller can
tell "your plan cannot" from "you cannot". See
[multi-tenancy.md](multi-tenancy.md#plans-and-feature-gating).

The one thing that machinery *doesn't* cover is metering — see
[the blocker](#the-blocker-no-usage-metering).

---

## Regulatory: e-invoicing is now law

**Cameroon's 2026 Finance Law makes real-time e-invoicing mandatory for all
taxable persons and transactions.** A central platform is to be built, with
accredited third-party providers permitted if they meet published standards.
Penalties for non-compliance hit where a business feels it: **disqualification
from expense deductions and VAT credits**.

This is not an add-on. It is a condition of an accounting product remaining
usable in Cameroon at all — and simultaneously the largest opportunity in this
document, because every taxable business in the country must buy compliant
invoicing software.

### What is not yet known

As of August 2026 the DGI has stated the obligation but **has not published**:

- the invoice format or schema,
- the clearance model (pre-clearance vs post-audit reporting),
- the rollout timeline or phasing,
- the accreditation criteria for third-party providers.

### What to do about it

**Build the seam, not the implementation.** Anyone shipping a Cameroon
e-invoicing integration today is guessing at a schema that has not been
published, and will rewrite it.

The seam is the same shape as the `Provisioner` protocol in
`platform/api/services/provisioning.py`, which was written for exactly this
reason — a slow, external, swappable dependency:

```python
class EInvoiceProvider(Protocol):
    async def submit(self, invoice: dict) -> ClearanceResult: ...
    async def status(self, submission_ref: str) -> ClearanceResult: ...
    async def cancel(self, submission_ref: str, reason: str) -> ClearanceResult: ...
```

with a `NoopEInvoiceProvider` as the default, and clearance state persisted per
invoice (`pending | submitted | cleared | rejected`, plus `clearance_ref` and
`rejection_reason`). Sales invoice posting in `services/sales_service.py` gains
one call into the provider.

That is days of work, it is useful regardless of what the specs turn out to be,
and it means the eventual implementation is one class rather than a refactor.

**Then pursue accreditation.** Being an accredited provider is a far stronger
moat than any product feature, and it is the natural extension of the OHADA /
SYSCOHADA localization we already have — the thing global products do badly.

**Do not** hardcode a guessed format. **Do not** promise customers a date.

---

## The portfolio

| Add-on | Feature flag | Effort | Revenue model | Verdict |
| --- | --- | --- | --- | --- |
| E-invoicing / DGI | `einvoicing` | seam: days · impl: unknown | per tenant + per submission | **Build the seam now** |
| Mobile money collections | `mobile_money` | 2–3 weeks | plan tier + % of volume | **Highest ROI** |
| WhatsApp delivery & dunning | `whatsapp` | 1–2 weeks | per tenant + metered messages | **Yes** |
| Payroll (CNPS / IRPP) | `payroll` | 4–6 weeks | per employee / month | **Yes, phase 2** |
| Bank statement import | `bank_import` | 1–2 weeks | included in a mid tier | Yes, cheap |
| POS / offline sales | `pos` | integrate | plan tier | Only on demand |
| AI bill capture (OCR) | `bill_capture` | ~2 weeks | metered per document | Nice-to-have |
| E-commerce connectors | `ecommerce` | integrate | plan tier | Only if asked |
| Working-capital lending | — | quarters | revenue share | Later, partner |

---

## Mobile money collections

The highest-value item that is entirely within our control.

| | Users (CM) | Integration | Cost |
| --- | --- | --- | --- |
| MTN MoMo | ~7M active | Collections + Disbursements API, sandbox → KYC → production keys | 0.5–1.5% merchant collection |
| Orange Money | ~5M active | Web Payment / M Payment API; customer confirms with a USSD OTP | operator-negotiated |
| Aggregators (CamPay, NotchPay, MeSomb, Monetbil, CinetPay, PayDunya) | both operators | one API, CMS plugins, local support | ~2–3.5% |

**Recommendation: aggregator first, direct later.** One integration instead of
two, and no separate merchant onboarding and KYC per operator. Revisit direct
MTN/Orange APIs once volume makes the 1–2 point spread worth the operational
overhead — the abstraction below makes that swap cheap.

```python
class PaymentProvider(Protocol):
    async def request_payment(self, *, amount, currency, payer, reference) -> PaymentIntent: ...
    async def status(self, intent_ref: str) -> PaymentStatus: ...
    # Webhook handling stays in the provider; the service layer sees only events.
```

### The actual prize is reconciliation, not acceptance

Accepting mobile money is table stakes; several products do it. What is
*uniquely* available to us is that we own both ends of the loop:

1. an invoice is issued from `/sales`,
2. the customer gets a pay link (email / WhatsApp),
3. settlement fires a webhook,
4. we post the receipt against **that** ERPNext invoice automatically, and it
   lands in the bank book and the aged receivables report with no re-keying.

That closed loop is what an SME feels daily, and it is the reason to build this
before anything else on the list. Standalone payment acceptance is a commodity;
payment-to-ledger reconciliation is not.

**Design notes:** webhooks must be idempotent (mobile money providers retry),
every intent needs an audit trail, and partial payments must be supported —
paying an invoice in instalments is normal here, not an edge case.

---

## WhatsApp delivery and dunning

Utility templates cost roughly **$0.01–0.10 per message** depending on country
and volume, with free-form replies free inside the 24-hour customer service
window. Volume discounts apply to utility templates; marketing templates get
none.

Use it for invoice delivery, payment reminders and receipt confirmation. In a
market where WhatsApp is the default business channel, emailing a PDF is simply
the inferior product.

Small build, high perceived value, and it meters naturally — which makes it a
good first customer for the metering work below. Pairs directly with mobile
money: the reminder carries the pay link.

---

## Payroll

The best-scaling revenue line in the list, because it prices per employee per
month rather than per tenant.

The rules are well-defined and stable:

- **CNPS** employee contribution 4.2% of gross, capped at a 750,000 XAF monthly
  ceiling; employer contributions on top
- **IRPP** on a progressive 10–35% scale
- plus **Additional Council Tax** and **Crédit Foncier**
- declarations to **DGI and CNPS by the 15th of the following month**

ERPNext HR sits underneath us already, so this is a curated UI plus a Cameroon
rules engine rather than a payroll system from scratch. It also benefits
directly from the account-role-map work described in the verticalization
discussion — payroll posts to accounts by *role*, not by hardcoded number.

Deliberately phase 2: it is the largest build here and it does not compound with
anything else the way payments and messaging do.

---

## Bank statement import

Feeds the bank book that already exists in `/finance`.

**Do this as file import (CSV / OFX / MT940), not as an API integration.** Open
banking effectively does not exist in CEMAC — 34 Cameroonian institutions are
tracked but with no confirmed aggregator coverage, and the global aggregators
(Plaid, Tink, TrueLayer) do not meaningfully reach the region. A "unified
Cameroon open banking API" initiative exists but is small and unproven; do not
build a dependency on it.

Import plus a reconciliation UI is a fraction of the work of a feed integration
and delivers most of the value. Revisit if COBAC-level open banking rules
materialise.

---

## Leverage, don't build

The Frappe/ERPNext ecosystem ships 150+ marketplace apps. Where one exists,
integrating or reselling beats building:

- **POS** — POSNext, GETPOS (multi-store, offline mode, touch UI)
- **E-commerce** — WooCommerce, Shopify, Amazon connectors
- **Payment gateways** — Stripe, PayPal, Razorpay and regional providers

Only build these ourselves if a customer's requirement genuinely cannot be met
by the existing app, and remember the rule from the verticalization discussion:
our value is the curated, opinionated layer, not re-implementing what ERPNext
already does.

Similarly **later, and by partnership rather than build**: working-capital
lending (our ledger is a genuine underwriting signal, but the regulatory burden
is a business in itself), insurance, and logistics tracking.

---

## The blocker: no usage metering

The control plane has plans and feature flags but **no usage metering or
rating**. Three of the strongest add-ons are inherently metered — WhatsApp
messages, e-invoice submissions, OCR documents — and payment revenue share needs
volume tracking.

Needed before the first metered add-on ships:

- a `usage_event` table in the control plane (tenant, metric, quantity,
  occurred_at, idempotency key),
- an ingest endpoint on `/internal` for the tenant app to report against,
- a monthly rollup + rating step against the plan's included allowance,
- surfacing in the operator console and, eventually, on an invoice.

It is not a large piece of work, but retrofitting billing after the fact — under
deadline, against live customer usage — is exactly the kind of thing that gets
done badly. Build it *before* the first metered feature, not alongside it.

---

## Recommended order

1. **E-invoicing seam** — days; hedges an existential regulatory risk and
   positions us for accreditation. Nothing about it depends on unpublished specs.
2. **Usage metering** — unblocks everything metered below.
3. **Mobile money via an aggregator** — the feature that sells the product; the
   auto-reconciliation loop is the real differentiator.
4. **WhatsApp delivery + dunning** — cheap, differentiating, and the first real
   consumer of metering.
5. **Payroll** — best per-seat revenue, once the above are stable.

Steps 1–4 are roughly a month of focused work, and together they move the
product from "ERP with white-labelling" to "the compliance-and-collections
platform for Cameroonian SMEs" — a considerably more defensible position.

---

## Sources

Retrieved August 2026.

**Regulatory** — treat as directional; verify with the DGI before implementing.

- [Cameroon to Implement Mandatory Real-Time E-Invoicing for VAT under the 2026 Finance Law — VATupdate](https://www.vatupdate.com/2026/02/09/cameroon-to-implement-mandatory-real-time-e-invoicing-for-vat-under-2026-finance-law/)
- [Cameroon 2026: Mandatory Real-Time E-Invoicing Introduced for All Taxable Persons — VATupdate](https://www.vatupdate.com/2026/03/20/cameroon-2026-mandatory-real-time-e-invoicing-introduced-for-all-taxable-persons/)
- [Direction Générale des Impôts (DGI)](https://www.impots.cm/) — the authoritative source once specs publish

**Payments**

- [MTN MoMo Developer Portal](https://momodeveloper.mtn.com/) · [MoMo Developer Community](https://momodevelopercommunity.mtn.com/)
- [Orange Money Web Payment / M Payment API — Orange Developer](https://developer.orange.com/apis/om-webpay)
- [Online Payment in Cameroon: MTN Money, Orange Money and 2026 Solutions — BEONWEB](https://www.beonweb.cm/en/blog/paiement-en-ligne-cameroun-mtn-orange-money-2026)
- [CamPay](https://campay.net/en/) · [Notch Pay — Mobile Money](https://developer.notchpay.co/accept-payments/mobile-money) · [Top Payment Gateways in Cameroon — Dusupay](https://www.dusupay.com/post/top-payment-gateways-in-cameroon)

**Messaging**

- [WhatsApp Business API Pricing 2026 — Uptail](https://www.uptail.ai/blog/whatsapp-business-api-pricing-2026-what-it-costs-and-how-billing-works)

**Payroll**

- [Payroll in Cameroon: Employer Guide, Tax & Compliance — Asanify](https://asanify.com/global-employer-of-record/cameroon/payroll/)
- [How to Run Payroll in Cameroon: Employment Taxes & Setup — Playroll](https://www.playroll.com/payroll/cameroon)

**Banking**

- [Open Banking in Cameroon: Banks, APIs & Regulations — OpenBankingTracker](https://www.openbankingtracker.com/country/cameroon)

**Ecosystem**

- [Frappe Cloud Marketplace](https://cloud.frappe.io/marketplace/search) · [Awesome Frappe](https://awesome-frappe.gavv.in/)
