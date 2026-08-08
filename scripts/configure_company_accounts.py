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

    def acc(number_and_name):
        """Account names are suffixed with the company abbreviation."""
        return "%s - %s" % (number_and_name, abbr)

    defaults = {
        # --- control accounts: these were actively wrong -------------------
        "default_receivable_account": acc("4111-Clients"),
        "default_payable_account": acc("4011-Fournisseurs"),
        "stock_received_but_not_billed": acc("4081-Fournisseurs"),
        "default_bank_account": acc("5211-Banques en monnaie nationale"),
        # --- were unset; each blocks a specific transaction type -----------
        "round_off_account": acc("6588-Autres charges diverses"),
        "stock_adjustment_account": acc("6031-Variations des stocks de marchandises"),
        "default_expense_account": acc("6011-Dans la Région"),
        "default_income_account": acc("7011-Dans la Région"),
        "default_inventory_account": acc("3111-Marchandises A1"),
        "default_cash_account": acc("5711-Caisse en monnaie nationale"),
    }

    # Without these every mode of payment falls through to the company's default
    # bank account — a cash receipt posts to the bank, and ERPNext then demands
    # a bank reference number for it.
    mode_accounts = {
        "Cash": acc("5711-Caisse en monnaie nationale"),
        "Bank Draft": acc("5211-Banques en monnaie nationale"),
        "Cheque": acc("5211-Banques en monnaie nationale"),
        "Wire Transfer": acc("5211-Banques en monnaie nationale"),
        "Credit Card": acc("5211-Banques en monnaie nationale"),
    }

    print("company: %s (abbr %s)" % (company, abbr))
    print()
    print("--- company default accounts " + "-" * 46)
    changed = skipped = 0
    for field, account in defaults.items():
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
    print("DONE — %d change(s), %d skipped" % (changed, skipped))


main()
