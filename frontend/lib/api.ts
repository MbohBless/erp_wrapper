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

export type LowStockItem = {
  item_code: string;
  item_name: string | null;
  warehouse: string;
  actual_qty: number;
  threshold: number;
};

export type ExpiringBatch = {
  batch_id: string;
  item_code: string;
  item_name: string | null;
  qty: number | null;
  expiry_date: string;
  days_left: number;
};

export type RevenueSegment = {
  label: string;
  amount: number;
  pct: number;
};

// Optional fields are the ones the server withholds by role — see
// backend services/dashboard_service.VISIBLE_FIELDS. A Store Keeper's response
// simply has no `revenue_today` key, so these are `undefined` rather than 0:
// zero is a real figure and must stay distinguishable from "not permitted".
export type DashboardSummary = {
  revenue_today?: number;
  outstanding_customers?: number;
  outstanding_suppliers?: number;
  inventory_value?: number;
  low_stock_count: number;
  revenue_trend?: TrendPoint[];
  recent_activity?: ActivityItem[];
  low_stock_items: LowStockItem[];
  expiring_batches: ExpiringBatch[];
  revenue_by_segment?: RevenueSegment[];
  top_customer?: RevenueSegment | null;
};

export const getDashboard = (token: string) =>
  api.get<DashboardSummary>(token, "/dashboard");

// ---- Formatting helpers ----

// XAF (Central African CFA franc) — Cameroon's currency, no minor units.
// Grouped with commas for readability, e.g. "3,423,250 FCFA".
const groupFmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
export const xaf = (n: number) => `${groupFmt.format(Math.round(n || 0))} FCFA`;

/** Parse a user-typed money string (with commas/currency) to a number. */
export const parseNum = (v: string | number): number => {
  if (typeof v === "number") return v;
  const n = parseFloat(String(v).replace(/[^\d.-]/g, ""));
  return Number.isNaN(n) ? 0 : n;
};

/** Group an input's digits with commas as the user types, e.g. "3500000" → "3,500,000". */
export const groupNum = (v: string): string => {
  const s = String(v);
  const neg = s.trim().startsWith("-");
  const digits = s.replace(/[^\d]/g, "");
  if (!digits) return neg ? "-" : "";
  return (neg ? "-" : "") + groupFmt.format(Number(digits));
};

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
