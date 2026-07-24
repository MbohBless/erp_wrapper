"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ReportDrawer, { type ReportKey } from "@/components/reports/ReportDrawer";
import { Icon } from "@/components/icons";
import { useAuth } from "@/lib/auth";

const REPORTS: { key: ReportKey; title: string; desc: string }[] = [
  { key: "current-stock", title: "Current Stock", desc: "On-hand quantities per item and warehouse." },
  { key: "low-stock", title: "Low Stock", desc: "Items at or below the low-stock threshold." },
  { key: "receivables", title: "Outstanding Receivables", desc: "Unpaid customer invoices by account." },
  { key: "payables", title: "Outstanding Payables", desc: "Unpaid supplier bills by account." },
  { key: "income-statement", title: "Income Statement", desc: "Profit & loss for a fiscal year (ERPNext)." },
  { key: "balance-sheet", title: "Balance Sheet", desc: "Assets, liabilities and equity (ERPNext)." },
];

export default function ReportsPage() {
  return (
    <AppShell>
      <ReportsContent />
    </AppShell>
  );
}

function ReportsContent() {
  const { token } = useAuth();
  const [open, setOpen] = useState<{ key: ReportKey; title: string } | null>(null);

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>EquiMed</span><span>›</span><span className="text-ink">Reports</span>
      </nav>
      <div className="mb-6">
        <h1 className="text-[32px] mb-1">Reports</h1>
        <p className="muted text-sm m-0">Operational and financial reporting across the business</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {REPORTS.map((r) => (
          <Blueprint key={r.key} className="p-[22px]">
            <div className="w-9 h-9 rounded-lg grid place-items-center bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent mb-4">
              <Icon name="reports" size={17} />
            </div>
            <div className="font-heading font-semibold text-base mb-1.5">{r.title}</div>
            <div className="text-[13px] muted mb-[18px] min-h-[36px]">{r.desc}</div>
            <button
              type="button"
              onClick={() => setOpen({ key: r.key, title: r.title })}
              className="h-9 px-4 rounded-lg border border-divider text-sm font-heading font-semibold hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]"
            >
              Generate
            </button>
          </Blueprint>
        ))}
      </div>

      {open && token && (
        <ReportDrawer
          reportKey={open.key}
          title={open.title}
          token={token}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}
