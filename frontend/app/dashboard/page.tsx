"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
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
import { getSetupStatus } from "@/lib/setup";
import { downloadReportPdf } from "@/lib/reports";

function SetupBanner() {
  const { token } = useAuth();
  const { data } = useQuery({
    queryKey: ["setup-status"],
    queryFn: () => getSetupStatus(token as string),
    enabled: !!token,
  });
  if (!data || data.setup_complete) return null;
  return (
    <a
      href="/setup"
      className="flex items-center gap-3 mb-5 px-4 py-3 rounded-xl border border-[color-mix(in_srgb,var(--color-accent)_35%,transparent)] bg-[color-mix(in_srgb,var(--color-accent)_10%,transparent)] hover:bg-[color-mix(in_srgb,var(--color-accent)_16%,transparent)] transition-colors"
    >
      <span className="grid place-items-center w-9 h-9 rounded-lg bg-accent text-bg shrink-0">
        <Icon name="finance" size={18} />
      </span>
      <span className="flex-1 min-w-0">
        <span className="block text-sm font-semibold">Finish setting up your books</span>
        <span className="block text-[13px] muted">Enter your opening balances once, and EquiMed takes over from there.</span>
      </span>
      <span className="btn btn-filled shrink-0">Start setup</span>
    </a>
  );
}

const PERIOD = new Intl.DateTimeFormat("en-GB", {
  month: "long",
  year: "numeric",
}).format(new Date());

function toCsv(rows: (string | number)[][]): string {
  return rows
    .map((r) => r.map((c) => {
      const s = String(c ?? "");
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(","))
    .join("\n");
}
function downloadCsv(filename: string, text: string) {
  const blob = new Blob(["﻿" + text], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Dashboard header actions: export (CSV / signed PDF) + a quick-create menu. */
function HeaderActions({ data }: { data: DashboardSummary }) {
  const { t } = useI18n();
  const { token } = useAuth();
  const router = useRouter();
  const [menu, setMenu] = useState<null | "export" | "new">(null);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setMenu(null); };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenu(null);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, []);

  const exportCsv = () => {
    const rows: (string | number)[][] = [
      ["EquiMed dashboard", PERIOD],
      [],
      ["Metric", "Value (XAF)"],
      [t("dashboard.kpi.revenue"), Math.round(data.revenue_today)],
      [t("dashboard.kpi.outstandingCustomers"), Math.round(data.outstanding_customers)],
      [t("dashboard.kpi.outstandingSuppliers"), Math.round(data.outstanding_suppliers)],
      [t("dashboard.kpi.inventoryValue"), Math.round(data.inventory_value)],
      [t("dashboard.lowStock"), data.low_stock_count],
      [],
      [t("dashboard.trend"), ""],
      ["Date", "Amount (XAF)"],
      ...data.revenue_trend.map((p) => [p.date, Math.round(p.amount)] as (string | number)[]),
      [],
      [t("dashboard.activity"), ""],
      ["Type", "Reference", "Party", "Amount (XAF)", "Date"],
      ...data.recent_activity.map((a) => [a.type, a.reference, a.party ?? "", Math.round(a.amount), a.date ?? ""] as (string | number)[]),
    ];
    downloadCsv(`equimed-dashboard-${new Date().toISOString().slice(0, 10)}.csv`, toCsv(rows));
    setMenu(null);
  };

  const exportPdf = async () => {
    setPdfError(null);
    setPdfBusy(true);
    try {
      await downloadReportPdf(token as string, "dashboard");
      setMenu(null);
    } catch (e) {
      setPdfError(e instanceof Error ? e.message : "Could not generate PDF");
    } finally {
      setPdfBusy(false);
    }
  };

  const NEW = [
    { key: "invoice", href: "/sales/new" },
    { key: "purchase", href: "/purchases/new" },
    { key: "customer", href: "/customers/new" },
    { key: "product", href: "/products/new" },
    { key: "stock", href: "/inventory/new?mode=receive" },
  ];

  return (
    <div className="flex gap-2.5" ref={ref}>
      <div className="relative">
        <button type="button" onClick={() => setMenu((m) => (m === "export" ? null : "export"))} aria-haspopup="menu" aria-expanded={menu === "export"} className="btn btn-outlined">
          <Icon name="export" size={15} />
          {t("dashboard.export")}
          <Icon name="chevronDown" size={14} />
        </button>
        {menu === "export" && (
          <div role="menu" className="absolute right-0 mt-2 w-60 z-30 rounded-xl border border-divider bg-bg shadow-[var(--shadow-lg)] p-1.5">
            <button type="button" role="menuitem" onClick={exportCsv} className="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-[color-mix(in_srgb,var(--color-text)_5%,transparent)] flex items-center gap-2.5">
              <Icon name="export" size={14} />{t("dashboard.exportCsv")}
            </button>
            <button type="button" role="menuitem" disabled={pdfBusy} onClick={exportPdf} className="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-[color-mix(in_srgb,var(--color-text)_5%,transparent)] flex items-center gap-2.5 disabled:opacity-60">
              <Icon name="reports" size={14} />{pdfBusy ? t("dashboard.exportPreparing") : t("dashboard.exportPdf")}
            </button>
            {pdfError && <div className="px-3 py-1.5 text-[12px] text-err">{pdfError}</div>}
          </div>
        )}
      </div>
      <div className="relative">
        <button type="button" onClick={() => setMenu((m) => (m === "new" ? null : "new"))} aria-haspopup="menu" aria-expanded={menu === "new"} className="btn btn-filled">
          <Icon name="plus" size={15} sw={1.8} />
          {t("dashboard.newRecord")}
          <Icon name="chevronDown" size={14} />
        </button>
        {menu === "new" && (
          <div role="menu" className="absolute right-0 mt-2 w-56 z-30 rounded-xl border border-divider bg-bg shadow-[var(--shadow-lg)] p-1.5">
            {NEW.map((n) => (
              <button
                key={n.key}
                type="button"
                role="menuitem"
                onClick={() => { setMenu(null); router.push(n.href); }}
                className="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-[color-mix(in_srgb,var(--color-text)_5%,transparent)] flex items-center gap-2.5"
              >
                <Icon name="plus" size={13} sw={1.8} />
                {t(`dashboard.new.${n.key}`)}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

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
      <SetupBanner />
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
        <HeaderActions data={data} />
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
