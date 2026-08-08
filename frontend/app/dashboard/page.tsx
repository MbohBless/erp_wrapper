"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import WidgetGrid from "@/components/dashboard/WidgetGrid";
import { Icon } from "@/components/icons";
import {
  type DashboardSummary,
  UnauthorizedError,
  getDashboard,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAppName } from "@/lib/branding";
import { getBrandingSettings } from "@/lib/dashboard";
import { useI18n } from "@/lib/i18n";
import { getSetupStatus } from "@/lib/setup";
import { downloadReportPdf } from "@/lib/reports";

function SetupBanner() {
  const { token } = useAuth();
  const appName = useAppName();
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
        <span className="block text-[13px] muted">Enter your opening balances once, and {appName} takes over from there.</span>
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
  const appName = useAppName();
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
    // The export is a second way out of the same data, so it follows the same
    // per-role rules: a figure the server withheld is absent from the file
    // rather than exported as NaN. `undefined` means "not permitted" here —
    // 0 is a real value and still exports.
    const metric = (label: string, v: number | undefined): (string | number)[][] =>
      v === undefined ? [] : [[label, Math.round(v)]];

    const rows: (string | number)[][] = [
      [`${appName} dashboard`, PERIOD],
      [],
      ["Metric", "Value (XAF)"],
      ...metric(t("dashboard.kpi.revenue"), data.revenue_today),
      ...metric(t("dashboard.kpi.outstandingCustomers"), data.outstanding_customers),
      ...metric(t("dashboard.kpi.outstandingSuppliers"), data.outstanding_suppliers),
      ...metric(t("dashboard.kpi.inventoryValue"), data.inventory_value),
      [t("dashboard.lowStock"), data.low_stock_count],
      ...(data.revenue_trend
        ? [
            [],
            [t("dashboard.trend"), ""],
            ["Date", "Amount (XAF)"],
            ...data.revenue_trend.map(
              (p) => [p.date, Math.round(p.amount)] as (string | number)[]
            ),
          ]
        : []),
      ...(data.recent_activity
        ? [
            [],
            [t("dashboard.activity"), ""],
            ["Type", "Reference", "Party", "Amount (XAF)", "Date"],
            ...data.recent_activity.map(
              (a) =>
                [a.type, a.reference, a.party ?? "", Math.round(a.amount), a.date ?? ""] as (
                  | string
                  | number
                )[]
            ),
          ]
        : []),
    ];
    const slug = appName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    downloadCsv(`${slug || "dashboard"}-dashboard-${new Date().toISOString().slice(0, 10)}.csv`, toCsv(rows));
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
  const { token } = useAuth();
  const appName = useAppName();

  // The layout is part of branding. If it fails to load we fall through to the
  // product default inside WidgetGrid rather than showing an empty page.
  const { data: branding } = useQuery({
    queryKey: ["branding-settings"],
    queryFn: () => getBrandingSettings(token as string),
    enabled: !!token,
    staleTime: 5 * 60_000,
  });

  return (
    <div className="eq-view">
      <SetupBanner />
      {/* Breadcrumb + heading */}
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>{appName}</span>
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

      <WidgetGrid layout={branding?.dashboard} data={data} />
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
