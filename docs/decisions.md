# Architecture decisions

Why the system works the way it does, for the choices that are not obvious from
reading the code — and, where a decision was reversed by evidence, what the
evidence was.

Each entry states the decision, the constraint that forced it, what was rejected
and why, and the consequence someone will trip over later. Entries are not
removed when superseded; a decision that turned out wrong is more useful written
down than deleted.

The RBAC matrix lives in [api.md](api.md), configuration in
[deployment.md](deployment.md), layering rules in
[coding_guidelines.md](coding_guidelines.md). This file is the reasoning behind
them.

---

## 1. A posted document is corrected by cancelling and re-posting it

**Decision.** `PUT /sales/{id}` and `PUT /purchases/{id}` cancel the document and
post a corrected copy carrying `amended_from`. They do not update it.

**Constraint.** ERPNext has no in-place update for a submitted document. Only
`allow_on_submit` fields can change, and none of the ones that matter are among
them. Cancel-then-amend is the only correction ERPNext supports.

**Consequence — the document number changes.** `ACC-SINV-2026-00007` is replaced
by `ACC-SINV-2026-00007-1`. If the customer already holds a printed invoice they
need the new number. Clients must read the id back from the response rather than
reuse the one they sent; the edit form says so before saving and names both
halves after.

**The two calls are not a transaction and cannot be.** If the cancel succeeds and
the re-post fails — a submit-time validation, a stock shortfall, a dropped
connection — the document is left cancelled with nothing standing in for it.
That state is recoverable: calling `PUT` again resumes from the cancelled
original. Which is exactly why it must not blindly re-post. Before re-posting it
looks for an existing amendment; if the first attempt did land and only the
response was lost, the same replacement comes back rather than a second invoice
for one sale.

**Refusals happen before anything is cancelled.** A paid invoice and an opening
balance are both rejected with 409 while the original is still live. ERPNext
would refuse them too — but only *after* the reversal, and as an opaque 502.

**Cancelled documents are excluded from the lists.** A reversed invoice beside
its replacement shows one sale twice, once for real and once for nothing. The
replacement carries `amended_from`, which is where the original stays visible.

### Rejected: deleting the cancelled original

Investigated on the live instance and declined. Five findings, any one of them
sufficient:

- The replacement holds a hard `amended_from` link back, and `delete_doc` scans
  for inbound links before deleting. The link is `read_only` with
  `allow_on_submit = 0`, so clearing it needs a raw `frappe.db.set_value`
  bypassing the document layer — code installed *inside* ERPNext.
- **It would reintroduce the bug it sits next to.** The double-post guard works
  by querying `amended_from`. Cut the link and a retried amend posts a second
  invoice for the same sale.
- The number is not recovered. The series counter sat at 95; Frappe only rewinds
  it when the *most recently issued* document is deleted, so the gap stays.
- `Sales Invoice` has `allow_rename = 0`, so the replacement cannot be renamed
  back to the original number either.
- Frappe snapshots deleted documents into `Deleted Document`. "Deleted" means
  moved somewhere nobody audits.

Cameroon is OHADA; SYSCOHADA expects accounting records to be retained and
corrections to be traceable. Reversal is the sanctioned correction.

---

## 2. The read model must expose everything the write model accepts

**Decision.** Any field `POST` accepts, `GET` returns. Non-negotiable for
documents that can be amended.

**Why.** A `PUT` replaces the whole document, so a field the API cannot read back
is a field an edit **clears**. Two live examples caught before shipping:

- Without `taxes_and_charges` in the read model, correcting an invoice takes the
  VAT off it.
- Without `update_stock`, the cancel returns goods to stock and the replacement
  never takes them out again — inventory inflated by a correction.

This is the same trap `PUT /settings/branding` already carries (see CLAUDE.md).
It is a property of the API shape, not of any one endpoint.

---

## 3. Line items carry the name they were billed under

**Decision.** `item_name` is read from ERPNext's line, which stamps it at save —
not looked up in the catalogue at read time. It is deliberately **not** sent back
on an amendment.

**Why.** The two differ the moment a product is renamed. What belongs on an
invoice already in a customer's hands is what it said then. Echoing the old name
back on a correction would pin it forever, so ERPNext refills it from the item
master instead.

Only available on `GET /{id}`. An ERPNext list query returns no child table at
all, so a list row has no lines to name.

---

## 4. A commissioned sale is a discount with a reason, not a commission

**Decision.** Two Custom Fields on Sales Invoice (`custom_is_commissioned`,
`custom_commission_agent`). ERPNext's native `sales_partner` / `commission_rate`
are deliberately unused.

**Why.** The customer is invoiced the *lower* price and no payout is owed — the
agent keeps the spread. `sales_partner` posts a commission **expense and a
liability**, which would put money on the books that nobody owes. The two model
different transactions; only one is happening here.

**The flag alone is worth little without the price it was discounted from**, so
every line records ERPNext's `price_list_rate`, read **server-side** from the
item's `custom_selling_price`. Never from the request: a list price the caller
supplies is a discount the caller invents.

Left unsent, ERPNext fills that field from the Standard Selling price list —
where six of thirteen items had no entry, so the line recorded a list price of
zero and the concession vanished. Selling below your own price left no trace
anywhere; that was the real defect under the feature request.

**A line charged at 0 is sent without a list price.** ERPNext recomputes `rate`
from `price_list_rate` when the rate is falsy, which would bill for a giveaway.

**The flag requires an agent and an agent requires the flag**, both 422. A flag
with no name answers nothing later; a name without the flag is a name no report
finds.

**Verified against the live instance on a draft invoice** — a draft posts no
ledger entries and deletes cleanly, so the question could be asked without
putting anything in the client's books:

- totals unchanged: `grand_total` is still `rate × qty`
- `rate` and `price_list_rate` both survive validation, including for items with
  no Item Price
- **ERPNext does not back-compute `discount_percentage`** on a server-side write.
  It stayed 0. Trusting that field would have reported every concession as zero,
  so the concession is derived from `(list − rate) × qty`.

**The price lock is a form control, not an API control.** The rate is read-only
unless the sale is marked commissioned, and unticking restores catalogue prices —
without that the flag is defeated in three clicks. It is not enforced server-side
because legitimate below-list sales exist that are not commissions (damaged
goods, a negotiated deal), and blocking those on a live system is the wrong
default. The data catches it either way: every line records the list price, so a
below-list sale is visible whether or not anyone ticked the box.

---

## 5. Lists page with a probe row, and their filters live on the server

**Decision.** Each page fetches `size + 1` rows. If the extra row comes back there
is a next page. No count query.

**Why not a total?** ERPNext's list API does not return one, so "of 312" costs a
second round trip per page load to display a number nobody acts on.

**The failure being fixed was silent truncation, not slowness.** The lists asked
for 200 rows and rendered all of them, so at 201 the 201st simply did not exist,
with nothing on screen to say so.

**Filters had to move server-side with it.** Filtering the fetched array filters
only the page in front of the user and silently hides every match on the others.
This forced a `disabled` filter into the customers, products and suppliers
endpoints, and moved the sales/purchases status filter out of the browser.
The products category dropdown moved to the reference endpoint for the same
reason: derived from the visible rows, filtering to a category becomes impossible
the moment its products fall to page two.

**Ordering needs a unique tiebreak.** `posting_date desc` alone leaves rows
sharing a date in whatever order the database returns, which is not stable
between requests — so a row appears on two pages while another appears on none.
`name` is appended. In a list that is a display glitch; in a sum it is a wrong
number (see §6).

**Records are fetched by id, never searched for in a page of the list.** Seven
edit pages did the latter, which works only while everything fits on one page.
Paginating made it reachable: editing the 26th customer loaded page one, failed
to find them, and sat on "Loading…" forever — not an error, not a 404, a spinner
with nothing behind it.

---

## 6. Nothing that gets summed is fetched with a cap

**Decision.** `FinanceRepository._fetch_all` pages until the data runs out.
Reaching the runaway ceiling is **logged**, not swallowed.

**Why.** Past a capped fetch a total is not visibly truncated — it is simply
smaller than the truth, by an amount nothing on the page can show, on the one
screen whose whole job is to be believed. Five caps were removed: 500 for the
summary, 1000 for the aged ledgers and cash book, 5000 for the opening balance,
100,000 for monthly movements.

The summary was the worst of them. It fetched every *submitted* invoice and
dropped the settled ones in Python, so the budget went on rows contributing
nothing — and because the sort is oldest-due-first, the rows that fell off the
end were the newest, which are the ones most likely to still be owed. It now asks
ERPNext for `outstanding_amount > 0`.

A silently short total is the failure this exists to prevent; swallowing the
ceiling one level down would reintroduce it.

### Rejected: ERPNext's native Accounts Receivable / Payable reports

Proposed, investigated against live data, and declined. The evidence:

| Check | Result |
| --- | --- |
| Totals | Identical — AR 33,162,500, AP 38,060,578 |
| Row sets | Identical, no extras, no duplicates |
| Ages, invoice by invoice | Identical (119 = 119, 114 = 114, …) |
| Their buckets vs their own total | **Do not reconcile** — 350,000 of not-yet-due invoices land in no bucket |
| Range boundaries | **Ignored.** 30/60/90/120, 0/30/60/90, 1/2/3/4 and 500/600/700/800 all returned identical output |
| Stability | Same bucket returned 7,216,500 and 7,566,500 on unchanged data |

Nothing to gain, and their range columns not summing to their own outstanding
total is disqualifying for a finance page. Ours reconcile.

**What was taken from the investigation:** the aged ledger's last bucket ran from
90 days to forever, putting a debt four months old beside one eight months old.
It splits at 120 — ERPNext's own ageing default, so the two reports can be read
side by side. On live data that separated 13.7M at three-to-four months from
25.4M beyond four months.

---

## 7. Roles: permissions are the product's, the role list is the deployment's

**Decision.** `DISABLED_ROLES` retires a role for one deployment. The RBAC matrix
itself is product-wide.

**Why the split.** One workspace having no sales reps is no reason for the next to
lose the option, so removing `Role.SALES` from the code would have been wrong.
Retired means *cannot be assigned*; the role keeps its permissions and its tests,
so re-enabling it is a line of `.env` rather than a restoration.

- **Enforced in the service on create *and* update**, not merely hidden in the
  dropdown. A policy only the UI knows is one anybody with a terminal can ignore,
  and the update path is how a retired role would actually get assigned.
- **Administrator is never retirable.** A deployment that disabled it could lock
  itself out of its own user administration with nothing left able to undo the
  setting.
- The user form asks the API which roles this workspace hands out, and still
  renders a role a user already holds even if it has since been retired —
  otherwise their record becomes unopenable.

**`docker-compose.yml` enumerates the backend's environment rather than reading
`.env`.** A setting absent from it reaches the app as its default, so the `.env`
line would have been accepted, ignored, and looked exactly like it worked.

### The accountant/manager boundary

The accountant runs the sales side and sees all the money; the supplier side
belongs to the manager.

- **Gained:** raising sales invoices, and adding/editing customers. The second
  follows from the first — without it a first-time buyer stalls the sale until a
  manager is free.
- **Lost:** suppliers and purchases entirely, and `POST /payments/pay` with them.
  Settling a bill is an operation on a purchase. Receipts stayed.
- **Unchanged:** the payables ledger, cash book and statements. "Sees the money
  but does not operate the supplier side" is where that lands.
- **Deleting a customer stayed where it was.** The router guarded create, update
  and delete with one dependency, so "let them add a buyer" silently also meant
  "let them delete one". Delete has its own guard now; a customer carries
  invoices and a ledger behind them.

**Known limit.** Only the role *list* is per-deployment. A second workspace's
accountant will also raise invoices and be locked out of purchases. If one wants
otherwise, that needs a per-tenant permission matrix — a feature, not a config
line.

---

## 8. Test doubles are held to ERPNext's behaviour, not to convenience

The fakes were repeatedly found **more permissive than ERPNext**, which is worse
than useless: it makes a test that exercises a rule prove nothing.

- Comparison operators (`>`, `<`, `>=`, `<=`) were ignored, so
  `["outstanding_amount", ">", 0]` — which the aged ledger already relied on —
  matched every row.
- The finance stub ignored filters and paging entirely, returning its whole
  dataset on every call.
- Dates are compared lexically, which is *why* ERPNext can filter on ISO strings.
  Coercing them to float and treating the failure as "no match" silently dropped
  every dated filter.

Two fixture files had to gain `docstatus: 1` once the stub started checking it —
they had never represented submitted documents.

**Every behavioural change in this document was mutation-tested**: break the fix,
watch the test go red, restore. That caught one bad test of its own — with
`start` ignored, a paging test looped forever instead of failing, and a test that
hangs on the bug it is meant to catch reports nothing. It is bounded now.

**The fake now refuses what ERPNext refuses.** Rules encoded, each standing for
a defect that shipped green: list queries return no child table, `posting_date`
is ignored without `set_posting_time`, tree roots cannot be selected, mandatory
fields and child rows are enforced, and a submitted document cannot be edited.
An unimplemented filter operator raises rather than matching every row.

Turning these on failed 29 tests, and every one traced to a **live defect**
rather than an over-strict rule: `ProductBase.category` still defaulted to
`"All Item Groups"`, and `integrations.create_customer` defaulted
`customer_group` to `"All Customer Groups"` — both tree roots, so any caller
that did not choose one was guaranteed a 417. The product test fixture had the
root written into it, and one assertion required it. The tests were holding the
bug in place.

Where no selectable group exists, both services now send **nothing** rather than
the root; ERPNext applies its own default and the record saves.

What this cannot do is find the *next* trap. It encodes rules already paid for,
so it is a regression net, not a discovery tool — which is the argument for a
real ERPNext in CI, still outstanding.

**A green suite is necessary, not sufficient.** Every ERPNext-facing change here
was exercised against the live instance. Where that meant writing, a **draft
document** was used and deleted: a draft posts no GL or stock entries, so the
question gets answered without entering the client's ledger.

---

## 9. Operating on a live instance

The client entered data throughout every change described here — invoices went
from 8 to 140 in a day. That shaped the process as much as the design.

- **Back up before every deploy** (`scripts/backup-remote.sh --force`), not only
  before data changes.
- **Verify a deploy by comparing commit hashes.** A failed pull leaves the
  previous build serving happily.
- **Rebuild only `backend` and `frontend`.** MariaDB, ERPNext and Redis are never
  recreated by an app deploy.
- **Never copy files to the server.** Commit, push, pull.
- **`.env` is edited line by line and never sourced** — sourcing executes it, and
  a value like `Biomedical Equipment & Supplies` would try to run "Supplies".
  Each edit leaves a `.pre-*` copy and the diff is checked.
- **Expectations in a verification script go stale.** Two "failures" in a
  post-deploy check were hardcoded snapshots taken hours earlier; the client had
  entered 27 more invoices. Assert against the database, not against a number
  remembered from the morning.

---

## Open items

| Item | Why it is not done |
| --- | --- |
| Item picker loads 500 rows rather than searching | Needs per-row search state; catalogue is 13 items. Ceiling written into the code. |
| RBAC matrix is product-wide | Per-tenant permissions is a feature, not a config line. Only one live tenant. |
| `custom_selling_price` and `Item Price` disagree on six items | Our invoices read the product directly, so they are unaffected; anything raised in the ERPNext desk would price those at zero. |
| No draft stage for invoices | Every invoice submits on save, so the first typo requires a cancellation. A draft stage would remove most amendments entirely. |
| No CI job against a real ERPNext | The strict fake encodes known traps only. Finding the next one needs the real thing — a scheduled job, not per-PR: site creation is 10–20 minutes. |
| Ageing does not split partial payments across buckets | ERPNext's report does; ours buckets each invoice wholly by due date. The two agree on totals today because there are few partial payments. |
