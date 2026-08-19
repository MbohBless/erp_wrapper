import { api } from "@/lib/http";

/** Curated SYSCOHADA account groups a budget line can track against. */
export const ACCOUNT_GROUPS: { prefix: string; label: string }[] = [
  { prefix: "70", label: "Revenue (sales)" },
  { prefix: "601", label: "Purchases — goods" },
  { prefix: "61", label: "Transport" },
  { prefix: "62", label: "External services & rent" },
  { prefix: "64", label: "Taxes & duties" },
  { prefix: "66", label: "Salaries & staff" },
  { prefix: "67", label: "Financial charges" },
  { prefix: "68", label: "Depreciation & provisions" },
  { prefix: "65", label: "Other expenses" },
];

export type BudgetLine = {
  category: string;
  account_prefix: string;
  kind: "income" | "expense";
  months_budget: number[]; // 12
  months_actual: number[]; // 12
  budget: number;          // year total
  actual: number;          // year total
  variance: number;
  pct: number;
};
export type BudgetReport = {
  fiscal_year: string;
  lines: BudgetLine[];
  total_budget: number;
  total_actual: number;
};
export type BudgetSaveLine = { category: string; account_prefix: string; months: number[] };

export const getBudget = (token: string, fiscalYear: string) =>
  api.get<BudgetReport>(token, "/budget", { fiscal_year: fiscalYear });

export const saveBudget = (
  token: string,
  input: { fiscal_year: string; lines: BudgetSaveLine[] }
) => api.put<BudgetReport>(token, "/budget", input);
