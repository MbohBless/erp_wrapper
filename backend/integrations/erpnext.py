"""ERPNext integration client.

The single choke point for all ERPNext communication (per coding guidelines).
A thin transport wrapper over the ERPNext REST resource API — no domain/business
logic. Domain mapping lives in the repositories that use this client.
"""

import json
from typing import Any

import httpx

from config import settings
from tenancy.context import current_tenant_or_none


class ERPNextError(Exception):
    """Raised when ERPNext returns an error or is unreachable."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ERPNextNotFound(ERPNextError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class ERPNextClient:
    """Transport wrapper over one ERPNext site.

    ``site_host`` is the multi-tenant lever. A Frappe bench serving many sites
    picks the site from the HTTP ``Host`` header, so several tenants can share
    one ``base_url`` while each reads and writes its own database. Leave it
    unset for a dedicated ERPNext instance, where ``base_url`` already
    identifies the tenant.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        site_host: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.erpnext_url).rstrip("/")
        self._api_key = api_key or settings.erpnext_api_key
        self._api_secret = api_secret or settings.erpnext_api_secret
        self.site_host = site_host or None

    # -- internals -----------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key and self._api_secret:
            headers["Authorization"] = f"token {self._api_key}:{self._api_secret}"
        if self.site_host:
            # Frappe resolves the site from Host; this is what keeps tenant A's
            # request off tenant B's database on a shared bench.
            headers["Host"] = self.site_host
        return headers

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.is_success:
            return
        # Try to surface ERPNext's error message.
        detail = resp.text
        try:
            body = resp.json()
            detail = body.get("exception") or body.get("message") or detail
        except (ValueError, AttributeError):
            pass
        if resp.status_code == 404:
            raise ERPNextNotFound(str(detail) or "Resource not found")
        raise ERPNextError(f"ERPNext error ({resp.status_code}): {detail}", 502)

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.request(
                    method, f"{self.base_url}{path}", headers=self._headers(), **kwargs
                )
        except httpx.RequestError as exc:
            raise ERPNextError(f"ERPNext is unreachable: {exc}", 502) from exc
        self._raise_for_status(resp)
        return resp

    # -- health --------------------------------------------------------------
    async def ping(self) -> bool:
        try:
            resp = await self._request("GET", "/api/method/ping")
            return resp.status_code == 200
        except ERPNextError:
            return False

    # -- generic DocType resource API ---------------------------------------
    async def list_documents(
        self,
        doctype: str,
        fields: list[str] | None = None,
        filters: list | None = None,
        limit: int = 20,
        start: int = 0,
        order_by: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit_page_length": limit, "limit_start": start}
        if fields:
            params["fields"] = json.dumps(fields)
        if filters:
            params["filters"] = json.dumps(filters)
        if order_by:
            params["order_by"] = order_by
        resp = await self._request("GET", f"/api/resource/{doctype}", params=params)
        return resp.json().get("data", [])

    async def get_document(self, doctype: str, name: str) -> dict:
        resp = await self._request("GET", f"/api/resource/{doctype}/{name}")
        return resp.json().get("data", {})

    async def create_document(self, doctype: str, data: dict) -> dict:
        resp = await self._request("POST", f"/api/resource/{doctype}", json=data)
        return resp.json().get("data", {})

    async def update_document(self, doctype: str, name: str, data: dict) -> dict:
        resp = await self._request(
            "PUT", f"/api/resource/{doctype}/{name}", json=data
        )
        return resp.json().get("data", {})

    async def delete_document(self, doctype: str, name: str) -> None:
        await self._request("DELETE", f"/api/resource/{doctype}/{name}")

    async def submit_document(self, doctype: str, name: str) -> dict:
        """Submit a submittable document (e.g. Stock Entry) so it affects stock.

        Uses frappe.client.submit, which expects the full document payload.
        """
        doc = await self.get_document(doctype, name)
        resp = await self._request(
            "POST",
            "/api/method/frappe.client.submit",
            json={"doc": json.dumps(doc)},
        )
        return resp.json().get("message", doc)

    async def run_report(self, report_name: str, filters: dict | None = None) -> dict:
        """Run an ERPNext Query Report (e.g. financial statements)."""
        params: dict[str, Any] = {"report_name": report_name}
        if filters:
            params["filters"] = json.dumps(filters)
        resp = await self._request(
            "GET", "/api/method/frappe.desk.query_report.run", params=params
        )
        return resp.json().get("message", {})

    async def call_method(
        self, method: str, args: dict | None = None, http_method: str = "POST"
    ) -> Any:
        """Call a whitelisted ERPNext server method and return its `message`."""
        kwargs: dict[str, Any] = {}
        if args:
            if http_method == "GET":
                kwargs["params"] = {k: json.dumps(v) if not isinstance(v, str) else v
                                    for k, v in args.items()}
            else:
                kwargs["json"] = args
        resp = await self._request(http_method, f"/api/method/{method}", **kwargs)
        return resp.json().get("message")


def get_erpnext_client() -> ERPNextClient:
    """FastAPI dependency provider for the ERPNext client.

    Builds the client from the *request's* tenant rather than from global
    settings — this one function is what makes every ERPNext-backed service in
    the app multi-tenant. Falls back to configuration outside a tenant-scoped
    request (startup tasks, scripts).
    """
    tenant = current_tenant_or_none()
    if tenant is None:
        return ERPNextClient()
    return ERPNextClient(
        base_url=tenant.erpnext_url or settings.erpnext_url,
        api_key=tenant.erpnext_api_key or settings.erpnext_api_key,
        api_secret=tenant.erpnext_api_secret or settings.erpnext_api_secret,
        site_host=tenant.erpnext_site,
    )


# ===========================================================================
# Domain wrapper functions — the high-level ERP integration API.
#
# These are the ONLY sanctioned way for the rest of the app to perform these
# ERP operations. ERPNext must never be called directly from outside this
# module; go through these wrappers (or the ERPNextClient methods above).
# ===========================================================================


async def create_customer(
    client: ERPNextClient,
    *,
    customer_name: str,
    customer_group: str = "All Customer Groups",
    customer_type: str = "Company",
    territory: str = "All Territories",
    tax_id: str | None = None,
) -> dict:
    """Create an ERPNext Customer."""
    payload: dict[str, Any] = {
        "customer_name": customer_name,
        "customer_group": customer_group,
        "customer_type": customer_type,
        "territory": territory,
    }
    if tax_id:
        payload["tax_id"] = tax_id
    return await client.create_document("Customer", payload)


async def create_invoice(
    client: ERPNextClient,
    *,
    customer: str,
    items: list[dict],
    due_date: str | None = None,
    posting_date: str | None = None,
    remarks: str | None = None,
    update_stock: bool = False,
    taxes_and_charges: str | None = None,
    submit: bool = True,
) -> dict:
    """Create a Sales Invoice. `items`: [{"item_code", "qty", "rate"}, ...].

    Submitted by default so it posts to the ledger.
    """
    payload: dict[str, Any] = {"customer": customer, "items": items}
    if due_date:
        payload["due_date"] = due_date
    if posting_date:
        # ERPNext ignores a supplied posting_date unless set_posting_time is
        # also set — it silently stamps today instead. Without this, backdating
        # an invoice appears to work and posts it to the wrong period, which is
        # an accounting error nobody sees until a period is closed.
        payload["posting_date"] = posting_date
        payload["set_posting_time"] = 1
    if remarks:
        payload["remarks"] = remarks
    if update_stock:
        payload["update_stock"] = 1
    if taxes_and_charges:
        payload["taxes_and_charges"] = taxes_and_charges
    doc = await client.create_document("Sales Invoice", payload)
    if submit:
        doc = await client.submit_document("Sales Invoice", doc["name"])
    return doc


async def create_purchase(
    client: ERPNextClient,
    *,
    supplier: str,
    items: list[dict],
    bill_no: str | None = None,
    posting_date: str | None = None,
    remarks: str | None = None,
    submit: bool = True,
) -> dict:
    """Create a Purchase Invoice (supplier bill). `items`: [{"item_code", "qty", "rate"}, ...].

    Submitted by default so it posts to the ledger.
    """
    payload: dict[str, Any] = {"supplier": supplier, "items": items}
    if bill_no:
        payload["bill_no"] = bill_no
    if posting_date:
        # ERPNext ignores a supplied posting_date unless set_posting_time is
        # also set — it silently stamps today instead. Without this, backdating
        # an invoice appears to work and posts it to the wrong period, which is
        # an accounting error nobody sees until a period is closed.
        payload["posting_date"] = posting_date
        payload["set_posting_time"] = 1
    if remarks:
        payload["remarks"] = remarks
    doc = await client.create_document("Purchase Invoice", payload)
    if submit:
        doc = await client.submit_document("Purchase Invoice", doc["name"])
    return doc


async def create_journal_entry(
    client: ERPNextClient,
    *,
    company: str,
    posting_date: str,
    accounts: list[dict],
    remark: str,
    is_opening: bool = False,
) -> dict:
    """Create + submit a Journal Entry. `accounts`: rows with account/debit/credit."""
    payload: dict[str, Any] = {
        "company": company,
        "posting_date": posting_date,
        "voucher_type": "Journal Entry",
        "user_remark": remark,
        "accounts": accounts,
    }
    if is_opening:
        payload["is_opening"] = "Yes"
    doc = await client.create_document("Journal Entry", payload)
    return await client.submit_document("Journal Entry", doc["name"])


async def create_opening_invoice(
    client: ERPNextClient,
    *,
    doctype: str,          # "Sales Invoice" | "Purchase Invoice"
    company: str,
    party: str,
    posting_date: str,
    due_date: str,
    amount: float,
    item_code: str,
    offset_account: str,   # balance-sheet account the opening balance offsets to
    bill_no: str | None = None,
) -> dict:
    """Create + submit an *opening* invoice (is_opening) so a pre-existing debt
    shows in the AR/AP ledger and can be paid off. Posts party ⇄ offset_account.
    """
    is_sales = doctype == "Sales Invoice"
    line: dict[str, Any] = {"item_code": item_code, "qty": 1, "rate": amount}
    line["income_account" if is_sales else "expense_account"] = offset_account
    payload: dict[str, Any] = {
        "company": company,
        "posting_date": posting_date,
        "set_posting_time": 1,
        "due_date": due_date,
        "is_opening": "Yes",
        "update_stock": 0,
        "items": [line],
    }
    payload["customer" if is_sales else "supplier"] = party
    if bill_no and not is_sales:
        payload["bill_no"] = bill_no
    doc = await client.create_document(doctype, payload)
    return await client.submit_document(doctype, doc["name"])


def _financial_filters(
    company: str,
    fiscal_year: str | None,
    from_date: str | None,
    to_date: str | None,
    periodicity: str,
) -> dict:
    filters: dict[str, Any] = {"company": company, "periodicity": periodicity}
    if fiscal_year:
        filters["filter_based_on"] = "Fiscal Year"
        filters["fiscal_year"] = fiscal_year
    elif from_date and to_date:
        filters["filter_based_on"] = "Date Range"
        filters["period_start_date"] = from_date
        filters["period_end_date"] = to_date
    return filters


async def get_balance_sheet(
    client: ERPNextClient,
    *,
    company: str,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    periodicity: str = "Yearly",
) -> dict:
    """Run the ERPNext "Balance Sheet" report."""
    filters = _financial_filters(
        company, fiscal_year, from_date, to_date, periodicity
    )
    return await client.run_report("Balance Sheet", filters)


async def get_income_statement(
    client: ERPNextClient,
    *,
    company: str,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    periodicity: str = "Yearly",
) -> dict:
    """Run the ERPNext "Profit and Loss Statement" (income statement) report."""
    filters = _financial_filters(
        company, fiscal_year, from_date, to_date, periodicity
    )
    return await client.run_report("Profit and Loss Statement", filters)
