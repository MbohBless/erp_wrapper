# Configure a company's default control accounts and payment-mode accounts.
#
#   docker compose exec -T erpnext-backend bench --site <site> console \
#       < scripts/configure_company_accounts.py
#
# WHY THIS EXISTS
#
# ERPNext's setup wizard builds the chart of accounts but does not reliably set
# the company's *default* accounts. On this deployment it left most of them
# unset and auto-picked semantically wrong ones for the rest — it matched by
# account-number prefix, so the receivable control became "4186-Clients,
# intérêts courus" (accrued interest) rather than "4111-Clients".
#
# The visible symptom is that the instance cannot post at all:
#
#   purchase invoice   -> "Please mention 'Round Off Account' in Company"
#   goods receipt      -> "Please enter Difference Account or set default
#                          Stock Adjustment Account for company"
#   cash receipt       -> "Reference No and Reference Date is mandatory for
#                          Bank transaction"   (because Mode of Payment "Cash"
#                          had no account, so it fell through to the bank)
#
# The quieter symptom is worse: with the wrong receivable control, every
# customer invoice posts to an accrued-interest account and the balance sheet is
# wrong in a way nobody notices until an audit.
#
# These are SYSCOHADA defaults for a distribution business. They restore a
# working, conventional configuration — they are not accounting advice, and the
# client's accountant should confirm them before real transactions are posted.
import frappe


def main():
    # Everything lives inside one function on purpose. `bench console` feeds the
    # file to IPython, which splits it into cells; module-level names defined in
    # one cell are not reliably visible inside a function defined in another, so
    # a top-level helper reading a top-level constant raises NameError.
    companies = frappe.get_all("Company", pluck="name")
    if not companies:
        print("no Company found — run the ERPNext setup wizard first")
        return
    company = companies[0]
    abbr = frappe.db.get_value("Company", company, "abbr")

    # The SYSCOHADA *number* is the stable identifier; how a chart carries it is
    # not. ERPNext ships two variants for Cameroon and they disagree:
    #
    #   Syscohada - Plan Comptable            account_number ""    account_name "4111-Clients"
    #   Syscohada - Plan Comptable avec code  account_number "4111" account_name "Clients"
    #
    # Composing "4111-Clients - ABBR" by hand matches the first and silently
    # misses the second — which is exactly how this script came to print DONE
    # having changed nothing at all, on a company that then could not post.
    rows = frappe.get_all(
        "Account",
        filters={"company": company, "is_group": 0},
        fields=["name", "account_number", "account_name"],
    )

    def resolve(number, hint):
        found = [r for r in rows if (r.account_number or "").strip() == number]
        if not found:
            # The number is glued to the name; tolerate "4111-x" and "4111 - x".
            found = [
                r for r in rows
                if (r.account_name or "").replace(" ", "").startswith(number + "-")
            ]
        if len(found) > 1:
            narrowed = [
                r for r in found if hint.lower() in (r.account_name or "").lower()
            ]
            found = narrowed or found
        return found[0].name if found else None

    # (SYSCOHADA number, a word from the account's name to break ties)
    wanted = {
        # --- control accounts: these were actively wrong -------------------
        "default_receivable_account": ("4111", "Clients"),
        "default_payable_account": ("4011", "Fournisseurs"),
        "stock_received_but_not_billed": ("4081", "Fournisseurs"),
        "default_bank_account": ("5211", "Banques"),
        # --- were unset; each blocks a specific transaction type -----------
        "round_off_account": ("6588", "charges diverses"),
        "stock_adjustment_account": ("6031", "Variations des stocks"),
        "default_expense_account": ("6011", "Région"),
        "default_income_account": ("7011", "Région"),
        "default_inventory_account": ("3111", "Marchandises"),
        "default_cash_account": ("5711", "Caisse"),
    }
    defaults = {field: resolve(*spec) for field, spec in wanted.items()}

    # Without these every mode of payment falls through to the company's default
    # bank account — a cash receipt posts to the bank, and ERPNext then demands
    # a bank reference number for it.
    cash, bank = resolve("5711", "Caisse"), resolve("5211", "Banques")
    mode_accounts = {
        "Cash": cash,
        "Bank Draft": bank,
        "Cheque": bank,
        "Wire Transfer": bank,
        "Credit Card": bank,
    }

    print("company: %s (abbr %s)" % (company, abbr))
    print()
    print("--- company default accounts " + "-" * 46)
    changed = skipped = 0
    unresolved = []
    for field, account in defaults.items():
        if account is None:
            number, hint = wanted[field]
            print("  !! %s: no account %s (%s) in this chart" % (field, number, hint))
            unresolved.append(field)
            skipped += 1
            continue
        # Never write a dangling reference: a missing or foreign account passes
        # silently here and fails later at posting time, which is a much worse
        # place to find out.
        if not frappe.db.exists("Account", account):
            print("  !! %s: %s does not exist — SKIPPED" % (field, account))
            skipped += 1
            continue
        if frappe.db.get_value("Account", account, "company") != company:
            print("  !! %s: %s belongs to another company — SKIPPED" % (field, account))
            skipped += 1
            continue
        before = frappe.db.get_value("Company", company, field) or "(unset)"
        if before == account:
            continue
        frappe.db.set_value("Company", company, field, account)
        print("  %-32s %-30s -> %s" % (field, str(before)[:28], account))
        changed += 1

    print()
    print("--- mode of payment accounts " + "-" * 46)
    for mode, account in mode_accounts.items():
        if not frappe.db.exists("Mode of Payment", mode):
            continue
        if account is None:
            print("  !! %s: no account to point it at" % mode)
            skipped += 1
            continue
        if not frappe.db.exists("Account", account):
            print("  !! %s: %s does not exist — SKIPPED" % (mode, account))
            skipped += 1
            continue
        doc = frappe.get_doc("Mode of Payment", mode)
        row = None
        for r in doc.accounts:
            if r.company == company:
                row = r
                break
        if row and row.default_account == account:
            continue
        if row:
            row.default_account = account
        else:
            doc.append("accounts", {"company": company, "default_account": account})
        doc.save(ignore_permissions=True)
        print("  %-16s -> %s" % (mode, account))
        changed += 1

    frappe.db.commit()
    frappe.clear_cache()
    print()
    # An unresolved default is not a cosmetic gap — each one of these blocks a
    # transaction type outright, or posts it to the wrong control account. Say
    # so in a way a caller can detect, rather than reporting DONE on a company
    # that cannot post.
    if unresolved:
        print("FAILED — %d default(s) could not be resolved in this chart: %s"
              % (len(unresolved), ", ".join(unresolved)))
        raise SystemExit(1)
    print("DONE — %d change(s), %d skipped" % (changed, skipped))


main()
