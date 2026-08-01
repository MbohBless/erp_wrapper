// Dashboard composition types + client for the tenant-configurable layout.
// The widget ids and viz names mirror `backend/schemas/branding.py`; the server
// is authoritative and rejects anything it does not recognise.

import { api } from "@/lib/http";
import type { Branding } from "@/lib/branding";

export type WidgetId =
  | "kpi.revenue"
  | "kpi.inventory_value"
  | "kpi.receivables"
  | "kpi.payables"
  | "chart.revenue_trend"
  | "chart.segment_mix"
  | "list.low_stock"
  | "list.expiring"
  | "table.recent_sales"
  | "feed.activity";

export type VizType = "line" | "area" | "bar" | "stacked-bar" | "donut" | "progress";

export type DashboardWidget = {
  id: WidgetId;
  visible: boolean;
  span: number;
  viz: VizType | null;
  title: string | null;
};

export type DashboardLayout = { widgets: DashboardWidget[] };

/** Which visualisations each widget accepts — drives the Settings editor. */
export const WIDGET_VIZ: Partial<Record<WidgetId, VizType[]>> = {
  "chart.revenue_trend": ["line", "area", "bar"],
  "chart.segment_mix": ["donut", "progress", "stacked-bar"],
};

export const WIDGET_LABELS: Record<WidgetId, string> = {
  "kpi.revenue": "Revenue KPI",
  "kpi.inventory_value": "Inventory value KPI",
  "kpi.receivables": "Receivables KPI",
  "kpi.payables": "Payables KPI",
  "chart.revenue_trend": "Revenue trend chart",
  "chart.segment_mix": "Revenue by segment",
  "list.low_stock": "Low stock list",
  "list.expiring": "Expiring batches list",
  "table.recent_sales": "Recent sales table",
  "feed.activity": "Activity feed",
};

export const ALL_WIDGET_IDS = Object.keys(WIDGET_LABELS) as WidgetId[];

export const DEFAULT_LAYOUT: DashboardLayout = {
  widgets: [
    { id: "kpi.revenue", visible: true, span: 1, viz: null, title: null },
    { id: "kpi.inventory_value", visible: true, span: 1, viz: null, title: null },
    { id: "kpi.receivables", visible: true, span: 1, viz: null, title: null },
    { id: "kpi.payables", visible: true, span: 1, viz: null, title: null },
    { id: "chart.revenue_trend", visible: true, span: 3, viz: "area", title: null },
    { id: "chart.segment_mix", visible: true, span: 1, viz: "progress", title: null },
    { id: "list.low_stock", visible: true, span: 2, viz: null, title: null },
    { id: "list.expiring", visible: true, span: 2, viz: null, title: null },
    { id: "table.recent_sales", visible: true, span: 3, viz: null, title: null },
    { id: "feed.activity", visible: true, span: 1, viz: null, title: null },
  ],
};

/** Full branding document (authenticated view), including the layout. */
export type BrandingSettings = Branding & {
  support_email: string;
  support_url: string;
  dashboard: DashboardLayout;
};

export const getBrandingSettings = (token: string) =>
  api.get<BrandingSettings>(token, "/settings/branding");

export const updateBrandingSettings = (
  token: string,
  input: Partial<BrandingSettings>
) => api.put<BrandingSettings>(token, "/settings/branding", input);

export const updateDashboardLayout = (token: string, layout: DashboardLayout) =>
  api.put<BrandingSettings>(token, "/settings/branding/dashboard", layout);

export const resetDashboardLayout = (token: string) =>
  api.post<BrandingSettings>(token, "/settings/branding/dashboard/reset", {});
