"""ERPNext-backed posting of first-time opening balances.

Posts a single opening Journal Entry for the summary balances (bank, cash,
inventory, equipment, loans) offset to an equity account, plus one *opening
invoice* per open receivable/payable so pre-existing debts show in the AR/AP
ledgers and can be paid off. Everything offsets to a single equity account, so
the books balance by construction.
"""

from integrations.erpnext import (
    ERPNextClient,
    ERPNextError,
    create_journal_entry,
    create_opening_invoice,
)
from schemas.setup import OpeningBalancesInput

# SYSCOHADA account number prefixes (this chart leaves account_number blank, so
# accounts are resolved by their name prefix "NNNN-…").
_PREFIX = {
    "bank": "5211",       # Banques en monnaie nationale
    "cash": "5711",       # Caisse en monnaie nationale
    "inventory": "3111",  # Marchandises
    "equipment": "2413",  # Matériel commercial
    "loan": "162",        # Emprunts et dettes (établissements de crédit)
    "equity": "1013",     # Capital — the single "Opening equity" offset
}


class SetupRepository:
    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def _company(self) -> str:
        rows = await self.client.list_documents("Company", fields=["name"], limit=1)
        if not rows:
            raise ERPNextError("No company is configured in ERPNext.", 400)
        return rows[0]["name"]

    async def _acc(self, company: str, prefix: str) -> str | None:
        rows = await self.client.list_documents(
            "Account", fields=["name"],
            filters=[["company", "=", company], ["is_group", "=", 0], ["name", "like", prefix + "-%"]],
            limit=1,
        )
        return rows[0]["name"] if rows else None

    async def _vehicle_item(self) -> str | None:
        rows = await self.client.list_documents(
            "Item", fields=["name"], filters=[["is_stock_item", "=", 1]], limit=1
        )
        return rows[0]["name"] if rows else None

    async def post_opening(self, data: OpeningBalancesInput) -> str:
        company = await self._company()
        acc = {k: await self._acc(company, p) for k, p in _PREFIX.items()}
        offset = acc["equity"]
        if not offset:
            raise ERPNextError("Could not find an equity account to post opening balances to.", 400)
        item = await self._vehicle_item()
        sd = data.start_date

        # ---- summary Journal Entry ----
        lines: list[dict] = []

        def dr(account: str | None, amount: float) -> None:
            if account and amount:
                lines.append({"account": account, "debit_in_account_currency": round(amount, 2),
                              "credit_in_account_currency": 0})

        def cr(account: str | None, amount: float) -> None:
            if account and amount:
                lines.append({"account": account, "debit_in_account_currency": 0,
                              "credit_in_account_currency": round(amount, 2)})

        dr(acc["bank"], data.bank)
        dr(acc["cash"], data.cash)
        dr(acc["inventory"], data.inventory_value)
        dr(acc["equipment"], data.equipment_value)
        loans_taken = sum(l.amount for l in data.loans if l.kind != "gave")
        cr(acc["loan"], loans_taken)

        # Balance the entry with the equity offset (owner's opening equity).
        tot_d = sum(x["debit_in_account_currency"] for x in lines)
        tot_c = sum(x["credit_in_account_currency"] for x in lines)
        diff = round(tot_d - tot_c, 2)
        if diff > 0:
            cr(offset, diff)
        elif diff < 0:
            dr(offset, -diff)

        opening_ref = ""
        if lines:
            je = await create_journal_entry(
                self.client, company=company, posting_date=sd, accounts=lines,
                remark="Opening balances (first-time setup)", is_opening=True,
            )
            opening_ref = je.get("name", "")

        # ---- open receivables / payables as opening invoices ----
        if item:
            for r in data.receivables:
                await create_opening_invoice(
                    self.client, doctype="Sales Invoice", company=company, party=r.party,
                    posting_date=r.date or sd, due_date=r.due_date or r.date or sd,
                    amount=r.amount, item_code=item, offset_account=offset,
                )
            for p in data.payables:
                await create_opening_invoice(
                    self.client, doctype="Purchase Invoice", company=company, party=p.party,
                    posting_date=p.date or sd, due_date=p.due_date or p.date or sd,
                    amount=p.amount, item_code=item, offset_account=offset, bill_no=p.reference,
                )
        return opening_ref
