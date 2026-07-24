"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Icon } from "@/components/icons";
import { xaf } from "@/lib/api";
import {
  type ReportResult,
  getFinanceReport,
  getFinanceSummary,
} from "@/lib/finance";
import { listStock } from "@/lib/inventory";

export type ReportKey =
  | "current-stock"
  | "low-stock"
  | "receivables"
  | "payables"
  | "income-statement"
  | "balance-sheet";

export default function ReportDrawer({
  reportKey,
  title,
  token,
  onClose,
}: {
  reportKey: ReportKey;
  title: string;
  token: string;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-[color-mix(in_srgb,#000_45%,transparent)]" onClick={onClose}>
      <div className="w-full max-w-[560px] h-full bg-bg border-l border-divider flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="h-[72px] shrink-0 flex items-center justify-between px-6 border-b border-divider">
          <div>
            <div className="text-[10px] tracking-[0.12em] uppercase text-accent">Report</div>
            <div className="font-heading font-semibold text-lg leading-tight">{title}</div>
          </div>
          <button type="button" onClick={onClose} className="icobtn grid place-items-center w-9 h-9 border border-divider muted" title="Close">
            <Icon name="close" size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto eq-scroll p-6">
          {(reportKey === "current-stock" || reportKey === "low-stock") && (
            <StockReport token={token} lowOnly={reportKey === "low-stock"} />
          )}
          {(reportKey === "receivables" || reportKey === "payables") && (
            <OutstandingReport token={token} kind={reportKey} />
          )}
          {(reportKey === "income-statement" || reportKey === "balance-sheet") && (
            <StatementReport token={token} kind={reportKey} />
          )}
        </div>
      </div>
    </div>
  );
}

const TH = "text-left text-[11px] tracking-[0.08em] uppercase font-semibold py-2.5 border-b border-divider muted";

function StockReport({ token, lowOnly }: { token: string; lowOnly: boolean }) {
  const { data, isLoading } = useQuery({
    queryKey: ["report-stock"],
    queryFn: () => listStock(token),
  });
  if (isLoading) return <Loading />;
  const rows = (data ?? []).filter((s) => (lowOnly ? s.actual_qty <= 10 : true));
  if (rows.length === 0) return <Empty text="No stock records." />;
  return (
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr>
          <th className={`${TH} pl-1`}>Product</th>
          <th className={TH}>Warehouse</th>
          <th className={`${TH} !text-right`}>Qty</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((s, i) => (
          <tr key={i} className="border-b border-solid divide-soft">
            <td className="py-2.5 pl-1 font-medium">{s.item_code}</td>
            <td className="py-2.5 muted">{s.warehouse}</td>
            <td className={`py-2.5 text-right font-semibold ${lowOnly ? "text-warn" : ""}`}>{s.actual_qty}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function OutstandingReport({ token, kind }: { token: string; kind: "receivables" | "payables" }) {
  const { data, isLoading } = useQuery({
    queryKey: ["report-finance"],
    queryFn: () => getFinanceSummary(token),
  });
  if (isLoading) return <Loading />;
  const rows = kind === "receivables" ? data?.outstanding_receivables : data?.outstanding_payables;
  const total = kind === "receivables" ? data?.receivables : data?.payables;
  if (!rows || rows.length === 0) return <Empty text="Nothing outstanding." />;
  return (
    <>
      <div className="flex justify-between items-baseline mb-4">
        <span className="text-sm muted">Total {kind}</span>
        <span className="font-heading font-semibold text-xl">{xaf(total ?? 0)}</span>
      </div>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr>
            <th className={`${TH} pl-1`}>{kind === "receivables" ? "Customer" : "Supplier"}</th>
            <th className={TH}>Reference</th>
            <th className={`${TH} !text-right`}>Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.reference} className="border-b border-solid divide-soft">
              <td className="py-2.5 pl-1 font-medium">{r.party}</td>
              <td className="py-2.5 muted">{r.reference}</td>
              <td className="py-2.5 text-right font-semibold">{xaf(r.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function StatementReport({ token, kind }: { token: string; kind: "income-statement" | "balance-sheet" }) {
  const [company, setCompany] = useState("");
  const [year, setYear] = useState("");
  const [result, setResult] = useState<ReportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await getFinanceReport(token, kind, { company, fiscal_year: year || undefined }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  const rows = result?.result ?? [];
  const columns = result?.columns ?? [];

  return (
    <div>
      <form onSubmit={run} className="flex flex-wrap items-end gap-2.5 mb-5">
        <div className="flex-1 min-w-[160px]">
          <label className="block text-xs muted mb-1.5">Company *</label>
          <input className="eq-field w-full px-3 py-2 text-sm" value={company} onChange={(e) => setCompany(e.target.value)} required placeholder="EquiMed SA" />
        </div>
        <div className="w-28">
          <label className="block text-xs muted mb-1.5">Fiscal year</label>
          <input className="eq-field w-full px-3 py-2 text-sm" value={year} onChange={(e) => setYear(e.target.value)} placeholder="2026" />
        </div>
        <button type="submit" disabled={busy || !company} className="h-[38px] px-4 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600 disabled:opacity-50">
          {busy ? "Running…" : "Run"}
        </button>
      </form>

      {error && <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">{error}</div>}

      {!result ? (
        <Empty text="Enter a company and run the report." />
      ) : rows.length === 0 ? (
        <Empty text="No data returned. Ensure ERPNext is connected and the company / fiscal year are correct." />
      ) : (
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr>
                {columns.map((c, i) => (
                  <th key={i} className={`${TH} ${i === 0 ? "pl-1" : "!text-right"}`}>{c.label ?? c.fieldname}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-b border-solid divide-soft">
                  {columns.map((c, j) => {
                    const v = c.fieldname ? row[c.fieldname] : undefined;
                    return (
                      <td key={j} className={`py-2 ${j === 0 ? "pl-1 font-medium" : "text-right muted"}`}>
                        {typeof v === "number" ? xaf(v) : String(v ?? "")}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Loading() {
  return <div className="py-10 text-center muted-2 text-sm">Loading…</div>;
}
function Empty({ text }: { text: string }) {
  return <div className="py-10 text-center muted-2 text-sm">{text}</div>;
}
