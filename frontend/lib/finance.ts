import { api } from "@/lib/http";

export type OutstandingItem = {
  party: string;
  reference: string;
  due_date: string | null;
  amount: number;
};

export type FinanceSummary = {
  receivables: number;
  payables: number;
  net_position: number;
  overdue_receivables: number;
  outstanding_receivables: OutstandingItem[];
  outstanding_payables: OutstandingItem[];
};

export const getFinanceSummary = (token: string) =>
  api.get<FinanceSummary>(token, "/finance/summary");

// ---- Aged AR / AP ledger ----
export type AgingBuckets = {
  current: number;
  d30: number;
  d60: number;
  d90: number;
  older: number;
  total: number;
};
export type LedgerRow = {
  party: string;
  reference: string;
  posting_date: string | null;
  due_date: string | null;
  grand_total: number;
  outstanding: number;
  age_days: number;
  bucket: string;
};
export type LedgerResult = { rows: LedgerRow[]; totals: AgingBuckets };

export const getReceivable = (token: string) =>
  api.get<LedgerResult>(token, "/finance/receivable");
export const getPayable = (token: string) =>
  api.get<LedgerResult>(token, "/finance/payable");

// ---- Cash / bank book ----
export type BookEntry = {
  date: string | null;
  voucher_type: string | null;
  voucher_no: string | null;
  party: string | null;
  against: string | null;
  debit: number;
  credit: number;
  balance: number;
  remarks: string | null;
};
export type BookResult = {
  accounts: string[];
  opening: number;
  closing: number;
  total_debit: number;
  total_credit: number;
  entries: BookEntry[];
};

export const getCashBook = (token: string) =>
  api.get<BookResult>(token, "/finance/cash-book");
export const getBankBook = (token: string) =>
  api.get<BookResult>(token, "/finance/bank-book");

// ---- Financial statements ----
export type StatementLine = {
  account: string;
  indent: number;
  amount: number;
  is_total: boolean;
};
export type StatementResult = { title: string; rows: StatementLine[] };

export const getIncomeStatement = (
  token: string,
  params: { company: string; fiscal_year?: string }
) => api.get<StatementResult>(token, "/finance/reports/income-statement", params);

export const getBalanceSheet = (
  token: string,
  params: { company: string; fiscal_year?: string }
) => api.get<StatementResult>(token, "/finance/reports/balance-sheet", params);

// ---- OHADA / SYSCOHADA statutory statements ----
export type OhadaLine = {
  code: string;
  label: string;
  amount: number;
  level: number;
  kind: "header" | "line" | "subtotal" | "total";
};
export type OhadaStatement = {
  title: string;
  subtitle: string;
  currency: string;
  fiscal_year: string | null;
  lines: OhadaLine[];
};

export const getOhadaIncomeStatement = (
  token: string,
  params: { company: string; fiscal_year?: string }
) => api.get<OhadaStatement>(token, "/finance/reports/ohada/compte-de-resultat", params);

export const getOhadaBalanceSheet = (
  token: string,
  params: { company: string; fiscal_year?: string }
) => api.get<OhadaStatement>(token, "/finance/reports/ohada/bilan", params);

export const getOhadaCashFlow = (
  token: string,
  params: { company: string; fiscal_year?: string }
) => api.get<OhadaStatement>(token, "/finance/reports/ohada/flux-de-tresorerie", params);
