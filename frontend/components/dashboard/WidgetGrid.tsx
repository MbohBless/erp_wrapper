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

const nf = new Intl.NumberFormat("en-GB");

/** Low-stock bins, straight from ERPNext. Empty is a real answer. */
function lowStockRows(data: DashboardSummary): ListRow[] {
  return (data.low_stock_items ?? []).map((it) => ({
    title: it.item_name || it.item_code,
    meta: `${it.warehouse} · at or below ${nf.format(it.threshold)}`,
    value: nf.format(it.actual_qty),
    // Out of stock is a different problem from running low; say so in colour.
    valueClass: it.actual_qty <= 0 ? "text-err" : "text-warn",
  }));
}

/** Batches with a real expiry date inside the horizon. */
function expiringRows(data: DashboardSummary): ListRow[] {
  return (data.expiring_batches ?? []).map((b) => {
    const urgent = b.days_left <= 30;
    const label =
      b.days_left <= 60
        ? `${b.days_left} day${b.days_left === 1 ? "" : "s"}`
        : `${Math.round(b.days_left / 30)} months`;
    return {
      title: b.item_name || b.item_code,
      meta: `Batch ${b.batch_id}${b.qty != null ? ` · ${nf.format(b.qty)} units` : ""}`,
      value: "",
      tag: {
        text: label,
        className: urgent
          ? "bg-[color-mix(in_srgb,var(--err-raw)_15%,transparent)] text-err"
          : "bg-[color-mix(in_srgb,var(--warn-raw)_16%,transparent)] text-warn",
      },
    };
  });
}

function revenueDelta(data: DashboardSummary): Delta | undefined {
  const trend = data.revenue_trend;
  if (!trend || trend.length < 2) return undefined;
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
        if (data.revenue_today === undefined) return null;
        return (
          <KpiCard
            icon="revenue"
            label={w.title || t("dashboard.kpi.revenue")}
            value={compact(data.revenue_today)}
            sub={t("dashboard.kpi.today")}
            delta={revenueDelta(data)}
            spark={(data.revenue_trend ?? []).map((p) => p.amount)}
          />
        );
      case "kpi.inventory_value":
        if (data.inventory_value === undefined) return null;
        return (
          <KpiCard
            icon="box3d"
            label={w.title || t("dashboard.kpi.inventoryValue")}
            value={compact(data.inventory_value)}
            sub={t("dashboard.kpi.onHand")}
          />
        );
      case "kpi.receivables":
        if (data.outstanding_customers === undefined) return null;
        return (
          <KpiCard
            icon="receivable"
            label={w.title || t("dashboard.kpi.receivables")}
            value={compact(data.outstanding_customers)}
            sub={t("dashboard.kpi.outstandingCustomers")}
          />
        );
      case "kpi.payables":
        if (data.outstanding_suppliers === undefined) return null;
        return (
          <KpiCard
            icon="payable"
            label={w.title || t("dashboard.kpi.payables")}
            value={compact(data.outstanding_suppliers)}
            sub={t("dashboard.kpi.outstandingSuppliers")}
          />
        );
      case "chart.revenue_trend":
        if (!data.revenue_trend) return null;
        return (
          <TrendChart
            data={data.revenue_trend}
            viz={(w.viz as TrendViz) || "area"}
            title={w.title}
          />
        );
      case "chart.segment_mix":
        if (!data.revenue_by_segment) return null;
        return (
          <SegmentMix
            viz={(w.viz as MixViz) || "progress"}
            title={w.title}
            segments={data.revenue_by_segment ?? []}
            topCustomer={data.top_customer}
          />
        );
      case "list.low_stock": {
        const rows = lowStockRows(data);
        return (
          <ListPanel
            title={
              w.title ||
              `${t("dashboard.lowStock")}${data.low_stock_count ? ` · ${data.low_stock_count}` : ""}`
            }
            dotColor="var(--warn)"
            rows={rows}
            emptyText={t("dashboard.noLowStock")}
            action={rows.length ? t("dashboard.viewAll") : undefined}
          />
        );
      }
      case "list.expiring": {
        const rows = expiringRows(data);
        return (
          <ListPanel
            title={w.title || t("dashboard.expiringSoon")}
            dotColor="var(--err)"
            rows={rows}
            emptyText={t("dashboard.noExpiring")}
            action={rows.length ? t("dashboard.viewAll") : undefined}
          />
        );
      }
      case "table.recent_sales":
        if (!data.recent_activity) return null;
        return <RecentSales items={data.recent_activity} />;
      case "feed.activity":
        if (!data.recent_activity) return null;
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
