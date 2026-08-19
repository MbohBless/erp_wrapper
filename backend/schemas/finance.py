"""Finance schemas (Pydantic V2): receivables/payables summary + report passthrough."""

from pydantic import BaseModel


class OutstandingItem(BaseModel):
    party: str
    reference: str
    due_date: str | None = None
    amount: float


class FinanceSummary(BaseModel):
    receivables: float
    payables: float
    net_position: float
    overdue_receivables: float
    outstanding_receivables: list[OutstandingItem]
    outstanding_payables: list[OutstandingItem]


# ---- Aged receivable / payable ledger ----
class AgingBuckets(BaseModel):
    current: float = 0    # not yet due
    d30: float = 0        # 1-30 days overdue
    d60: float = 0        # 31-60
    d90: float = 0        # 61-90
    # 91-120 was previously folded into `older`, which put a debt four months
    # late beside one a year late and gave collections nothing to sort on. The
    # boundary is 120 to match ERPNext's own ageing, so the two reports can be
    # read side by side.
    d120: float = 0       # 91-120
    older: float = 0      # over 120
    total: float = 0


class LedgerRow(BaseModel):
    party: str
    reference: str
    posting_date: str | None = None
    due_date: str | None = None
    grand_total: float
    outstanding: float
    age_days: int
    bucket: str  # "Current" | "1-30" | "31-60" | "61-90" | "91-120" | "120+"


class LedgerResult(BaseModel):
    rows: list[LedgerRow]
    totals: AgingBuckets


# ---- Cash / bank book (from the general ledger) ----
class BookEntry(BaseModel):
    date: str | None = None
    voucher_type: str | None = None
    voucher_no: str | None = None
    party: str | None = None
    against: str | None = None
    debit: float = 0
    credit: float = 0
    balance: float = 0
    remarks: str | None = None


class BookResult(BaseModel):
    accounts: list[str]
    opening: float
    closing: float
    total_debit: float
    total_credit: float
    entries: list[BookEntry]


# ---- Financial statements (normalised report rows) ----
class StatementLine(BaseModel):
    account: str
    indent: int = 0
    amount: float = 0
    is_total: bool = False


class StatementResult(BaseModel):
    title: str
    rows: list[StatementLine]


# ---- Trial balance (closing debit/credit per leaf account) ----
class TrialBalanceRow(BaseModel):
    account: str
    debit: float = 0
    credit: float = 0


class TrialBalanceResult(BaseModel):
    title: str = "Trial Balance"
    rows: list[TrialBalanceRow]
    total_debit: float = 0
    total_credit: float = 0


# ---- Cash flow statement (direct method, from the cash & bank ledger) ----
class CashFlowLine(BaseModel):
    label: str
    amount: float = 0


class CashFlowResult(BaseModel):
    title: str = "Cash Flow Statement"
    opening: float = 0
    closing: float = 0
    total_in: float = 0
    total_out: float = 0
    net_change: float = 0
    inflows: list[CashFlowLine]
    outflows: list[CashFlowLine]
