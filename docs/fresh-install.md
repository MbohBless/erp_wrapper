# Fresh install — handing a clean instance to a client

Follow this in order. Steps 3 and 4 are not optional: until they run, the
instance looks fine and **cannot post a single transaction**.

Time: about 30 minutes, most of it waiting for ERPNext to build the chart of
accounts.

---

## 0. Decide these before you start

Two of them can never be changed afterwards. Get them right the first time.

| | Value | Changeable later? |
| --- | --- | --- |
| Company name | Quality Biomedicals | ✅ yes (`frappe.rename_doc`) |
| **Company abbreviation** | **QBM** | ❌ **never** — `set_only_once` |
| Country | Cameroon | ⚠️ painful |
| Currency | XAF | ⚠️ painful |
| **Chart of accounts** | **SYSCOHADA** | ❌ not once anything is posted |
| Fiscal year start | 1 January | ⚠️ painful |

> **The abbreviation is why a reset is sometimes the only option.** It is
> suffixed onto every account name (`4111-Clients - QBM`), and ERPNext marks the
> field `set_only_once`. There is no rename utility and `Company.after_rename`
> does not touch it. Choosing "TD" and wanting "QBM" later means doing all of
> this again.

---

## 1. Erase the current instance

```bash
ssh <host>
cd /opt/equimed

NEW_ADMIN_EMAIL="admin@qbmedicals.com" \
NEW_ADMIN_PASSWORD="<the app password>" \
./scripts/factory-reset.sh
```

It takes a final backup first, then asks twice — the site name, then `ERASE`.

It removes the ERPNext site and the application database, clears the stale
ERPNext API keys, writes the new admin credentials into `.env`, and recreates an
empty site. It keeps your secrets, R2 backups, certificates and firewall rules.

---

## 2. ERPNext setup wizard

The production overlay does not publish the desk at all, so there is nothing to
tunnel *to* yet. Publish it on the server's loopback first:

```bash
# on the server
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
               -f docker-compose.desk.yml up -d erpnext-nginx

# from your laptop
ssh -L 8080:127.0.0.1:8080 <host>         # leave this running
```

> `127.0.0.1` is resolved **by the server**. A tunnel to `erpnext-nginx` fails
> with *"Temporary failure in name resolution"* — that name exists only inside
> the Docker network, not to the host's resolver.

Put it back when the wizard and steps 3–4 are done:

```bash
docker compose up -d --force-recreate erpnext-nginx
```

Open <http://localhost:8080>, sign in as `Administrator` with `ADMIN_PASSWORD`
from `.env`, and complete the wizard:

| Field | Value |
| --- | --- |
| Language | English |
| Country | **Cameroon** |
| Time zone | Africa/Douala |
| Currency | **XAF** |
| Company Name | **Quality Biomedicals** |
| Company Abbreviation | **check this before continuing** — see below |
| Chart of Accounts | **SYSCOHADA** |
| Fiscal year | 1 Jan – 31 Dec |

> **ERPNext auto-fills the abbreviation from the company name and it is
> `set_only_once`.** "Quality BioMedicals Sarl" yields `QBS`, "Quality
> Biomedicals" yields `QB`. Whatever you want, type it explicitly before
> continuing — it is suffixed onto every account, warehouse and cost-centre
> name, and the only way to change it afterwards is another full reset.

Building the SYSCOHADA chart takes a few minutes and creates ~1,400 accounts.

---

## 3. Configure the company's default accounts — **required**

The wizard builds the chart but does not reliably set the company's *default*
accounts, and what it guesses it matches by account-number prefix, which on
SYSCOHADA picks semantically wrong ones.

```bash
docker compose cp scripts/configure_company_accounts.py erpnext-backend:/tmp/cfg.py
echo 'exec(open("/tmp/cfg.py").read())' \
  | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console
```

Skip this and the instance **cannot post**:

- purchase invoice → *"Please mention 'Round Off Account' in Company"*
- goods receipt → *"Please enter Difference Account or set default Stock Adjustment Account"*
- cash receipt → *"Reference No and Reference Date is mandatory for Bank transaction"*

The quieter fault is worse: on this deployment the wizard chose
`4186-Clients, intérêts courus` (accrued interest) as the receivable control, so
every customer invoice would have posted to the wrong account, and nothing
complains until an audit.

**Have the client's accountant confirm the mapping** before real transactions.
The script restores a conventional configuration; it is not accounting advice.

> Pipe a single `exec(open(...).read())` line rather than redirecting the file
> in. `bench console` hands stdin to IPython, which splits it into cells and
> dedents function bodies — a multi-line script raises `NameError` on its own
> helpers.

---

## 4. Install the Custom Fields — **required**

```bash
docker compose cp scripts/install_custom_fields.py erpnext-backend:/tmp/cf.py
echo 'exec(open("/tmp/cf.py").read(), globals())' \
  | docker compose exec -T erpnext-backend bench --site "$SITE_NAME" console
```

> Pass `globals()` to `exec`. Without it the source runs where locals and
> globals differ, so a name bound at the top of the file is invisible to a
> function defined below it — `NameError` on the script's own helpers.

The API stores anything ERPNext has no native field for on a `custom_*` Custom
Field — contact person, phone, manufacturer, selling price, ticket status.
Without them those attributes are **silently dropped**: a customer saves with no
phone number and no error is reported.

---

## 5. ERPNext API keys

The old keys belonged to a user in a database that no longer exists.

In the desk: **User list → Administrator → Settings → API Access → Generate Keys**.
Copy both, then:

```bash
cd /opt/equimed
sed -i 's|^ERPNEXT_API_KEY=.*|ERPNEXT_API_KEY=<key>|'       .env
sed -i 's|^ERPNEXT_API_SECRET=.*|ERPNEXT_API_SECRET=<secret>|' .env
docker compose up -d backend
```

---

## 6. Application branding

Sign in to the app at your domain as the admin from step 1, then
**Settings → Branding**:

- Product name, short name, tagline
- Logo (light and dark), favicon
- Theme colours — green and red for Quality Biomedicals
- Dashboard layout

This is the *application's* identity and is per-tenant. It is separate from the
ERPNext **Company**, which is business data and prints on invoices.

---

## 7. Verify before handing over

```bash
./scripts/watchdog.sh --status         # every check should pass
```

Then in the app, confirm each of these actually works — they are the four that
have broken before:

- [ ] create a customer *(needs the custom fields)*
- [ ] create a product; tick **Track batches** on one *(needed for expiry)*
- [ ] receive stock into **Stores**, not "All Warehouses" *(a group node is refused)*
- [ ] raise and pay a sales invoice *(needs step 3)*

Finally:

- [ ] `./scripts/backup-remote.sh --force`, then `./scripts/restore.sh --latest --dry-run`
- [ ] set `ALERT_WEBHOOK_URL` and run `./scripts/watchdog.sh --test`
- [ ] change the admin password from the one in `.env`
- [ ] store `BACKUP_ENCRYPTION_KEY` somewhere other than the server — without it
      every backup is unreadable

---

## Keep a clean baseline

Once steps 1–6 are done and before any real data is entered, snapshot it:

```bash
./scripts/backup-remote.sh --force
# then copy the newest bundle to a name retention will never prune:
#   rclone copyto R2:<bucket>/equimed/backup-<...>.tar.gz.enc \
#                 R2:<bucket>/equimed/pristine-configured.tar.gz.enc
```

Retention only sweeps objects named `backup-*`, so a `pristine-*` object
survives indefinitely. That bundle is a configured, empty instance — the
fastest way back if a demo or a trial needs undoing.
