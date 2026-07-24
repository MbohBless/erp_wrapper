"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import { UnauthorizedError, shortDate, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { type FinanceSummary, type OutstandingItem, getFinanceSummary } from "@/lib/finance";

export default function FinancePage() {
  return (
    <AppShell>
      <FinanceContent />
    </AppShell>
  );
}

function FinanceContent() {
  const { token, logout } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["finance-summary"],
    queryFn: () => getFinanceSummary(token as string),
    enabled: !!token,
  });

  useEffect(() => {
    if (error instanceof UnauthorizedError) logout();
  }, [error, logout]);

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>EquiMed</span>
        <span>›</span>
        <span className="text-ink">Finance</span>
      </nav>
      <div className="mb-5">
        <h1 className="text-[32px] mb-1">Finance</h1>
        <p className="muted text-sm m-0">
          Receivables, payables and payment reconciliation
        </p>
      </div>

      {isLoading ? (
        <Loading />
      ) : error ? (
        <div className="blueprint p-10 text-center muted">
          Could not load finance data.
        </div>
      ) : data ? (
        <FinanceView data={data} />
      ) : null}
    </div>
  );
}

function FinanceView({ data }: { data: FinanceSummary }) {
  const netOk = data.net_position >= 0;
  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
        <StatCard label="Receivables" value={xaf(data.receivables)} />
        <StatCard label="Payables" value={xaf(data.payables)} />
        <StatCard
          label="Net position"
          value={`${netOk ? "+" : ""}${xaf(data.net_position)}`}
          valueClass={netOk ? "text-ok" : "text-err"}
        />
        <StatCard
          label="Overdue"
          value={xaf(data.overdue_receivables)}
          valueClass="text-err"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <OutstandingTable
          title="Outstanding receivables"
          partyLabel="Customer"
          rows={data.outstanding_receivables}
        />
        <OutstandingTable
          title="Outstanding payables"
          partyLabel="Supplier"
          rows={data.outstanding_payables}
        />
      </div>
    </>
  );
}

function StatCard({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <Blueprint className="p-5">
      <div className="text-[11px] tracking-[0.1em] uppercase muted">{label}</div>
      <div className={`font-heading font-semibold text-[26px] mt-1 ${valueClass ?? ""}`}>
        {value}
      </div>
    </Blueprint>
  );
}

function OutstandingTable({
  title,
  partyLabel,
  rows,
}: {
  title: string;
  partyLabel: string;
  rows: OutstandingItem[];
}) {
  return (
    <Blueprint className="p-0 overflow-hidden">
      <div className="px-5 py-4 border-b border-divider font-heading font-semibold text-base">
        {title}
      </div>
      {rows.length === 0 ? (
        <div className="py-12 text-center muted-2 text-sm">Nothing outstanding.</div>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="muted">
              <th className="text-left text-[11px] tracking-[0.08em] uppercase font-semibold px-5 py-2.5 border-b border-divider">
                {partyLabel}
              </th>
              <th className="text-left text-[11px] tracking-[0.08em] uppercase font-semibold py-2.5 border-b border-divider">
                Due
              </th>
              <th className="text-right text-[11px] tracking-[0.08em] uppercase font-semibold px-5 py-2.5 border-b border-divider">
                Amount
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.reference} className="border-b border-solid divide-soft">
                <td className="px-5 py-3 font-medium">{r.party}</td>
                <td className="py-3 muted">{shortDate(r.due_date)}</td>
                <td className="px-5 py-3 text-right font-semibold">{xaf(r.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Blueprint>
  );
}

function Loading() {
  return (
    <div className="animate-pulse">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="blueprint h-[104px]" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="blueprint h-[260px]" />
        <div className="blueprint h-[260px]" />
      </div>
    </div>
  );
}
