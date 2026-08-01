"use client";

import type { ReactNode } from "react";

import ActivityFeed from "@/components/ActivityFeed";
import KpiCard, { type Delta } from "@/components/KpiCard";
import ListPanel, { type ListRow } from "@/components/ListPanel";
import RecentSales from "@/components/RecentSales";
import SegmentMix, { type MixViz } from "@/components/SegmentMix";
import TrendChart, { type TrendViz } from "@/components/TrendChart";
import { type DashboardSummary, compact } from "@/lib/api";
import { DEFAULT_LAYOUT, type DashboardLayout, type DashboardWidget } from "@/lib/dashboard";
import { useI18n } from "@/lib/i18n";

/**
 * Renders the dashboard from the tenant's saved layout.
 *
 * The page no longer hard-codes which panels exist or where they sit — it maps
 * over `layout.widgets` and asks the registry for each one. Adding a widget is
 * a new entry here plus a new id in `schemas/branding.py`; re-arranging one is
 * a data change a tenant makes in Settings.
 */

// Tailwind needs literal class names, so spans are a lookup rather than a
// template string — a computed `xl:col-span-${n}` would be purged from the CSS.
const SPAN_CLASS: Record<number, string> = {
  1: "xl:col-span-1",
  2: "sm:col-span-2 xl:col-span-2",
  3: "sm:col-span-2 xl:col-span-3",
  4: "sm:col-span-2 xl:col-span-4",
};

// Illustrative rows for panels without an item-level endpoint yet.
const LOW_STOCK: ListRow[] = [
  { title: "Insulin Glargine 100IU", meta: "Cold Room A · reorder at 150", value: "88", valueClass: "text-err" },
  { title: "Salbutamol Inhaler", meta: "WH Yaoundé · reorder at 300", value: "210", valueClass: "text-warn" },
  { title: "Paracetamol 1g Injection", meta: "WH Yaoundé · reorder at 400", value: "320", valueClass: "text-warn" },
];
const EXPIRING: ListRow[] = [
  { title: "Metformin 850mg", meta: "Batch MET-7781 · 1,900 units", value: "", tag: { text: "34 days", className: "bg-[color-mix(in_srgb,var(--err-raw)_15%,transparent)] text-err" } },
  { title: "Artemether/Lumefantrine", meta: "Batch ACT-9901 · 12,400 units", value: "", tag: { text: "2 months", className: "bg-[color-mix(in_srgb,var(--warn-raw)_16%,transparent)] text-warn" } },
  { title: "Amoxicillin 500mg", meta: "Batch AMX-2409 · 4,200 units", value: "", tag: { text: "5 months", className: "bg-[color-mix(in_srgb,var(--warn-raw)_16%,transparent)] text-warn" } },
];

function revenueDelta(data: DashboardSummary): Delta | undefined {
  const trend = data.revenue_trend;
  if (trend.length < 2) return undefined;
  const [prev, last] = [trend[trend.length - 2].amount, trend[trend.length - 1].amount];
  if (!prev) return undefined;
  const pct = Math.round(((last - prev) / prev) * 100);
  return {
    dir: pct >= 0 ? "up" : "down",
    text: `${Math.abs(pct)}%`,
    tone: pct >= 0 ? "ok" : "err",
  };
}

export default function WidgetGrid({
  layout,
  data,
}: {
  layout: DashboardLayout | null | undefined;
  data: DashboardSummary;
}) {
  const { t } = useI18n();
  const widgets = (layout?.widgets?.length ? layout.widgets : DEFAULT_LAYOUT.widgets).filter(
    (w) => w.visible !== false
  );

  const render = (w: DashboardWidget): ReactNode => {
    switch (w.id) {
      case "kpi.revenue":
        return (
          <KpiCard
            icon="revenue"
            label={w.title || t("dashboard.kpi.revenue")}
            value={compact(data.revenue_today)}
            sub={t("dashboard.kpi.today")}
            delta={revenueDelta(data)}
            spark={data.revenue_trend.map((p) => p.amount)}
          />
        );
      case "kpi.inventory_value":
        return (
          <KpiCard
            icon="box3d"
            label={w.title || t("dashboard.kpi.inventoryValue")}
            value={compact(data.inventory_value)}
            sub={t("dashboard.kpi.onHand")}
          />
        );
      case "kpi.receivables":
        return (
          <KpiCard
            icon="receivable"
            label={w.title || t("dashboard.kpi.receivables")}
            value={compact(data.outstanding_customers)}
            sub={t("dashboard.kpi.outstandingCustomers")}
          />
        );
      case "kpi.payables":
        return (
          <KpiCard
            icon="payable"
            label={w.title || t("dashboard.kpi.payables")}
            value={compact(data.outstanding_suppliers)}
            sub={t("dashboard.kpi.outstandingSuppliers")}
          />
        );
      case "chart.revenue_trend":
        return (
          <TrendChart
            data={data.revenue_trend}
            viz={(w.viz as TrendViz) || "area"}
            title={w.title}
          />
        );
      case "chart.segment_mix":
        return <SegmentMix viz={(w.viz as MixViz) || "progress"} title={w.title} />;
      case "list.low_stock":
        return (
          <ListPanel
            title={
              w.title ||
              `${t("dashboard.lowStock")}${data.low_stock_count ? ` · ${data.low_stock_count}` : ""}`
            }
            dotColor="var(--warn)"
            rows={LOW_STOCK}
            action={t("dashboard.viewAll")}
          />
        );
      case "list.expiring":
        return (
          <ListPanel
            title={w.title || t("dashboard.expiringSoon")}
            dotColor="var(--err)"
            rows={EXPIRING}
            action={t("dashboard.viewAll")}
          />
        );
      case "table.recent_sales":
        return <RecentSales items={data.recent_activity} />;
      case "feed.activity":
        return <ActivityFeed items={data.recent_activity} />;
      default:
        // An unknown id means the server knows a widget this build does not.
        // Skip it rather than crashing the whole dashboard.
        return null;
    }
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 items-start">
      {widgets.map((w) => {
        const content = render(w);
        if (!content) return null;
        return (
          <div key={w.id} className={SPAN_CLASS[w.span] ?? SPAN_CLASS[1]}>
            {content}
          </div>
        );
      })}
    </div>
  );
}
