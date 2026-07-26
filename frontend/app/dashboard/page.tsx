"use client";

import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import ActivityFeed from "@/components/ActivityFeed";
import AppShell from "@/components/AppShell";
import KpiCard, { type Delta } from "@/components/KpiCard";
import ListPanel, { type ListRow } from "@/components/ListPanel";
import RecentSales from "@/components/RecentSales";
import SegmentMix from "@/components/SegmentMix";
import TrendChart from "@/components/TrendChart";
import { Icon } from "@/components/icons";
import {
  type DashboardSummary,
  UnauthorizedError,
  compact,
  getDashboard,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

const PERIOD = new Intl.DateTimeFormat("en-GB", {
  month: "long",
  year: "numeric",
}).format(new Date());

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

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardContent />
    </AppShell>
  );
}

function DashboardContent() {
  const { token, logout } = useAuth();
  const { t } = useI18n();
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => getDashboard(token as string),
    enabled: !!token,
  });

  useEffect(() => {
    if (error instanceof UnauthorizedError) logout();
  }, [error, logout]);

  if (isLoading) return <Loading />;
  if (error)
    return (
      <div className="blueprint p-10 text-center muted">
        {t("dashboard.loadError")}
      </div>
    );
  if (!data) return null;
  return <DashboardView data={data} />;
}

function DashboardView({ data }: { data: DashboardSummary }) {
  const { t } = useI18n();
  const revenueDelta = useMemo<Delta | undefined>(() => {
    const t = data.revenue_trend;
    if (t.length < 2) return undefined;
    const [prev, last] = [t[t.length - 2].amount, t[t.length - 1].amount];
    if (!prev) return undefined;
    const pct = Math.round(((last - prev) / prev) * 100);
    return {
      dir: pct >= 0 ? "up" : "down",
      text: `${Math.abs(pct)}%`,
      tone: pct >= 0 ? "ok" : "err",
    };
  }, [data.revenue_trend]);

  const spark = data.revenue_trend.map((p) => p.amount);

  return (
    <div className="eq-view">
      {/* Breadcrumb + heading */}
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>EquiMed</span>
        <span>›</span>
        <span className="text-ink">{t("dashboard.title")}</span>
      </nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-6">
        <div>
          <h1 className="text-[32px] mb-1">{t("dashboard.title")}</h1>
          <p className="muted text-sm m-0">{t("dashboard.subtitle")} · {PERIOD}</p>
        </div>
        <div className="flex gap-2.5">
          <button className="btn btn-outlined">
            <Icon name="export" size={15} />
            {t("dashboard.export")}
          </button>
          <button className="btn btn-filled">
            <Icon name="plus" size={15} sw={1.8} />
            {t("dashboard.newRecord")}
          </button>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
        <KpiCard
          icon="revenue"
          label={t("dashboard.kpi.revenue")}
          value={compact(data.revenue_today)}
          sub={t("dashboard.kpi.today")}
          delta={revenueDelta}
          spark={spark}
        />
        <KpiCard
          icon="box3d"
          label={t("dashboard.kpi.inventoryValue")}
          value={compact(data.inventory_value)}
          sub={t("dashboard.kpi.onHand")}
        />
        <KpiCard
          icon="receivable"
          label={t("dashboard.kpi.receivables")}
          value={compact(data.outstanding_customers)}
          sub={t("dashboard.kpi.outstandingCustomers")}
        />
        <KpiCard
          icon="payable"
          label={t("dashboard.kpi.payables")}
          value={compact(data.outstanding_suppliers)}
          sub={t("dashboard.kpi.outstandingSuppliers")}
        />
      </div>

      {/* Trend + segment mix */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] gap-4 mb-4">
        <TrendChart data={data.revenue_trend} />
        <SegmentMix />
      </div>

      {/* Low stock + expiring */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <ListPanel
          title={`${t("dashboard.lowStock")}${data.low_stock_count ? ` · ${data.low_stock_count}` : ""}`}
          dotColor="var(--warn)"
          rows={LOW_STOCK}
          action={t("dashboard.viewAll")}
        />
        <ListPanel
          title={t("dashboard.expiringSoon")}
          dotColor="var(--err)"
          rows={EXPIRING}
          action={t("dashboard.viewAll")}
        />
      </div>

      {/* Recent sales + activity */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-4">
        <RecentSales items={data.recent_activity} />
        <ActivityFeed items={data.recent_activity} />
      </div>
    </div>
  );
}

function Loading() {
  return (
    <div className="animate-pulse">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="blueprint h-[168px]" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] gap-4 mb-4">
        <div className="blueprint h-[300px]" />
        <div className="blueprint h-[300px]" />
      </div>
      <div className="blueprint h-[220px]" />
    </div>
  );
}
