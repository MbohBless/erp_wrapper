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

export type ReportColumn = { label?: string; fieldname?: string };
export type ReportResult = {
  columns?: ReportColumn[];
  result?: Record<string, unknown>[];
  [k: string]: unknown;
};

export const getFinanceReport = (
  token: string,
  kind: "income-statement" | "balance-sheet",
  params: { company: string; fiscal_year?: string }
) => api.get<ReportResult>(token, `/finance/reports/${kind}`, params);
