import { api } from "@/lib/http";

// Re-exported so existing `import { UnauthorizedError } from "@/lib/api"` keeps working.
export { UnauthorizedError } from "@/lib/http";

export type TrendPoint = { date: string; amount: number };

export type ActivityItem = {
  type: string;
  reference: string;
  party: string | null;
  amount: number;
  date: string | null;
};

export type DashboardSummary = {
  revenue_today: number;
  outstanding_customers: number;
  outstanding_suppliers: number;
  inventory_value: number;
  low_stock_count: number;
  revenue_trend: TrendPoint[];
  recent_activity: ActivityItem[];
};

export const getDashboard = (token: string) =>
  api.get<DashboardSummary>(token, "/dashboard");

// ---- Formatting helpers ----

// XAF (Central African CFA franc) — Cameroon's currency, no minor units.
const xafFmt = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "XAF",
  maximumFractionDigits: 0,
});
export const xaf = (n: number) => xafFmt.format(n || 0);

// Compact figures the way the EquiMed design shows them: "28.4M", "840K".
export function compact(n: number): string {
  const v = Math.abs(n || 0);
  if (v >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (v >= 1_000) return Math.round(n / 1_000) + "K";
  return String(Math.round(n || 0));
}
export const xafCompact = (n: number) => `${compact(n)} XAF`;

const dateFmt = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
});
export const shortDate = (s?: string | null) =>
  s ? dateFmt.format(new Date(s)) : "—";
