import { api } from "@/lib/http";

export type OpeningItem = {
  party: string;
  reference?: string | null;
  date?: string | null;
  due_date?: string | null;
  amount: number;
};
export type LoanItem = {
  lender: string;
  kind: string; // "took" | "gave"
  amount: number;
  rate?: number | null;
  end_date?: string | null;
};
export type BudgetItem = { category: string; yearly: number };

export type OpeningBalancesInput = {
  start_date: string;
  bank: number;
  cash: number;
  inventory_value: number;
  equipment_value: number;
  receivables: OpeningItem[];
  payables: OpeningItem[];
  loans: LoanItem[];
  budgets: BudgetItem[];
};

export type SetupStatus = {
  setup_complete: boolean;
  start_date: string;
  opening_ref: string;
  posted_at: string | null;
};

export const getSetupStatus = (token: string) =>
  api.get<SetupStatus>(token, "/setup/status");

export const postOpeningBalances = (token: string, input: OpeningBalancesInput) =>
  api.post<SetupStatus>(token, "/setup/opening-balances", input);
