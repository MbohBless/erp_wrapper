"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import { Icon } from "@/components/icons";
import { xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type CashFlowResult,
  type StatementResult,
  type TrialBalanceResult,
  getBalanceSheet,
  getCashFlow,
  getFinanceSummary,
  getIncomeStatement,
  getTrialBalance,
} from "@/lib/finance";
import { useI18n } from "@/lib/i18n";
import { listStock, listWarehouses } from "@/lib/inventory";
import { type ReportKey, type ReportParams, downloadReportPdf } from "@/lib/reports";
import { useAppName } from "@/lib/branding";
import { useCompanyName } from "@/lib/company";

type NeedKind = "statement" | "stock" | "outstanding";
type ReportDef = {
  key: ReportKey;
  title: string;
  desc: string;
  icon: string;
  kind: NeedKind;
};

const GROUPS: { gid: string; items: ReportDef[] }[] = [
  {
    gid: "financial",
    items: [
      { key: "income-statement", title: "Income Statement", desc: "Profit & loss for a fiscal year.", icon: "finance", kind: "statement" },
      { key: "balance-sheet", title: "Balance Sheet", desc: "Assets, liabilities and equity.", icon: "finance", kind: "statement" },
      { key: "trial-balance", title: "Trial Balance", desc: "Debit & credit for every account.", icon: "finance", kind: "statement" },
      { key: "cash-flow", title: "Cash Flow Statement", desc: "Cash in and out over the period.", icon: "finance", kind: "statement" },
      { key: "receivables", title: "Outstanding Receivables", desc: "Unpaid customer invoices.", icon: "receivable", kind: "outstanding" },
      { key: "payables", title: "Outstanding Payables", desc: "Unpaid supplier bills.", icon: "payable", kind: "outstanding" },
    ],
  },
  {
    gid: "inventory",
    items: [
      { key: "current-stock", title: "Current Stock", desc: "On-hand quantities per item.", icon: "inventory", kind: "stock" },
      { key: "low-stock", title: "Low Stock", desc: "Items at or below the threshold.", icon: "alert", kind: "stock" },
    ],
  },
];
const ALL = GROUPS.flatMap((g) => g.items);

export default function ReportsPage() {
  return (
    <AppShell>
      <ReportsContent />
    </AppShell>
  );
}

function ReportsContent() {
  const appName = useAppName();
  const { token } = useAuth();
  const { t } = useI18n();
  const [selected, setSelected] = useState<ReportKey>("income-statement");
  const defaultCompany = useCompanyName();
  const [company, setCompany] = useState("");
  useEffect(() => {
    setCompany((c) => c || defaultCompany);
  }, [defaultCompany]);
  const [fiscalYear, setFiscalYear] = useState(String(new Date().getFullYear()));
  const [warehouse, setWarehouse] = useState("");
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const def = ALL.find((r) => r.key === selected) as ReportDef;

  const params: ReportParams = useMemo(() => {
    if (def.kind === "statement")
      return { company, fiscal_year: fiscalYear || undefined };
    if (def.kind === "stock") return { warehouse: warehouse || undefined };
    return {};
  }, [def.kind, company, fiscalYear, warehouse]);

  const download = useMutation({
    mutationFn: () => downloadReportPdf(token as string, selected, params),
    onError: (e) => setDownloadError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>{appName}</span><span>›</span><span className="text-ink">{t("reports.title")}</span>
      </nav>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[32px] mb-1">{t("reports.title")}</h1>
          <p className="muted text-sm m-0">{t("reports.subtitle")}</p>
        </div>
        <div className="flex items-center gap-2 text-[12px] muted">
          <span className="grid place-items-center w-5 h-5 rounded-full bg-[color-mix(in_srgb,var(--ok-raw)_18%,transparent)] text-ok">
            <Icon name="check" size={12} sw={2.4} />
          </span>
          {t("reports.signedNote")}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[264px_1fr] gap-5 items-start">
        {/* Selector rail */}
        <div className="rounded-2xl border border-divider bg-bg p-2.5">
          {GROUPS.map((group) => (
            <div key={group.gid} className="mb-1.5 last:mb-0">
              <div className="text-[10px] tracking-[0.12em] uppercase muted-3 px-3 pt-3 pb-1.5">{t(`reports.group.${group.gid}`)}</div>
              {group.items.map((r) => {
                const active = r.key === selected;
                return (
                  <button
                    key={r.key}
                    type="button"
                    onClick={() => { setSelected(r.key); setDownloadError(null); }}
                    className={`relative w-full text-left flex items-start gap-3 px-3 py-2.5 rounded-xl transition-colors ${
                      active ? "bg-[color-mix(in_srgb,var(--color-accent)_12%,transparent)]" : "hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]"
                    }`}
                  >
                    {active && <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded bg-accent" />}
                    <span className={`shrink-0 mt-0.5 ${active ? "text-accent" : "muted-2"}`}><Icon name={r.icon} size={17} /></span>
                    <span className={`text-sm leading-tight ${active ? "font-semibold text-ink" : ""}`}>{t(`reports.item.${r.key}.title`)}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {/* Detail */}
        <div className="rounded-2xl border border-divider bg-bg overflow-hidden">
          <div className="flex flex-wrap items-start justify-between gap-4 p-6 border-b border-divider">
            <div className="min-w-0">
              <h2 className="font-heading font-semibold text-xl">{t(`reports.item.${selected}.title`)}</h2>
              <p className="muted text-sm mt-1 mb-0">{t(`reports.item.${selected}.desc`)}</p>
            </div>
            <button
              type="button"
              onClick={() => { setDownloadError(null); download.mutate(); }}
              disabled={download.isPending}
              className="btn btn-filled shrink-0"
            >
              <Icon name="export" size={15} sw={1.8} />
              {download.isPending ? t("reports.preparing") : t("reports.download")}
            </button>
          </div>

          {/* Params */}
          {def.kind === "statement" && (
            <div className="px-6 pt-5 grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-4">
              <Field label={t("reports.company")}>
                <input className={FIELD} value={company} onChange={(e) => setCompany(e.target.value)} placeholder={defaultCompany || "Company name"} />
              </Field>
              <Field label={t("reports.fiscalYear")}>
                <input className={FIELD} value={fiscalYear} onChange={(e) => setFiscalYear(e.target.value)} placeholder="2026" />
              </Field>
            </div>
          )}
          {def.kind === "stock" && token && (
            <WarehousePicker token={token} value={warehouse} onChange={setWarehouse} label={t("reports.warehouse")} allLabel={t("reports.allWarehouses")} />
          )}

          {downloadError && (
            <div className="mx-6 mt-5 text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px]">
              {downloadError}
            </div>
          )}

          {/* Preview */}
          <div className="p-6">
            <div className="text-[11px] tracking-[0.1em] uppercase muted-3 mb-3">{t("reports.preview")}</div>
            {token && def.kind === "outstanding" && <OutstandingPreview token={token} kind={selected as "receivables" | "payables"} />}
            {token && def.kind === "stock" && <StockPreview token={token} lowOnly={selected === "low-stock"} warehouse={warehouse} />}
            {token && def.kind === "statement" && (selected === "income-statement" || selected === "balance-sheet") && <StatementPreview token={token} kind={selected} company={company} fiscalYear={fiscalYear} />}
            {token && selected === "trial-balance" && <TrialBalancePreview token={token} company={company} fiscalYear={fiscalYear} />}
            {token && selected === "cash-flow" && <CashFlowPreview token={token} company={company} fiscalYear={fiscalYear} />}
          </div>
        </div>
      </div>
    </div>
  );
}

const FIELD = "eq-field w-full px-3 py-2.5 text-sm";
const TH = "text-left text-[11px] tracking-[0.08em] uppercase font-semibold py-2.5 border-b border-divider muted";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[13px] muted mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function WarehousePicker({ token, value, onChange, label, allLabel }: { token: string; value: string; onChange: (v: string) => void; label: string; allLabel: string }) {
  const { data } = useQuery({ queryKey: ["warehouses"], queryFn: () => listWarehouses(token) });
  return (
    <div className="px-6 pt-5">
      <Field label={label}>
        <select className={`${FIELD} max-w-xs`} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">{allLabel}</option>
          {(data ?? []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
      </Field>
    </div>
  );
}

function OutstandingPreview({ token, kind }: { token: string; kind: "receivables" | "payables" }) {
  const { data, isLoading } = useQuery({ queryKey: ["report-finance"], queryFn: () => getFinanceSummary(token) });
  if (isLoading) return <Muted text="Loading…" />;
  const rows = kind === "receivables" ? data?.outstanding_receivables : data?.outstanding_payables;
  const total = kind === "receivables" ? data?.receivables : data?.payables;
  if (!rows || rows.length === 0) return <Muted text="Nothing outstanding." />;
  return (
    <>
      <div className="flex justify-between items-baseline mb-3">
        <span className="text-sm muted">Total {kind}</span>
        <span className="font-heading font-semibold text-xl num">{xaf(total ?? 0)}</span>
      </div>
      <Table
        head={[kind === "receivables" ? "Customer" : "Supplier", "Reference", "Amount"]}
        rightCols={[2]}
        rows={rows.map((r) => [r.party, r.reference, xaf(r.amount)])}
      />
    </>
  );
}

function StockPreview({ token, lowOnly, warehouse }: { token: string; lowOnly: boolean; warehouse: string }) {
  const { data, isLoading } = useQuery({ queryKey: ["report-stock"], queryFn: () => listStock(token) });
  if (isLoading) return <Muted text="Loading…" />;
  let rows = (data ?? []).filter((s) => (lowOnly ? s.actual_qty <= 10 : true));
  if (warehouse) rows = rows.filter((s) => s.warehouse === warehouse);
  if (rows.length === 0) return <Muted text="No stock records." />;
  return (
    <Table
      head={["Product", "Warehouse", "On-hand qty"]}
      rightCols={[2]}
      rows={rows.map((s) => [s.item_code, s.warehouse, String(s.actual_qty)])}
      emphasizeRight={lowOnly}
    />
  );
}

function StatementPreview({ token, kind, company, fiscalYear }: { token: string; kind: "income-statement" | "balance-sheet"; company: string; fiscalYear: string }) {
  const { t } = useI18n();
  const [result, setResult] = useState<StatementResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = useMutation({
    mutationFn: () => {
      const fn = kind === "income-statement" ? getIncomeStatement : getBalanceSheet;
      return fn(token, { company, fiscal_year: fiscalYear || undefined });
    },
    onSuccess: (r) => { setError(null); setResult(r); },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div>
      <button type="button" onClick={() => run.mutate()} disabled={run.isPending || !company} className="btn btn-outlined mb-4">
        {run.isPending ? t("reports.generating") : result ? t("reports.refreshPreview") : t("reports.loadPreview")}
      </button>
      {error && <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px] mb-3">{error}</div>}
      {!result ? (
        <Muted text={t("reports.statementPrompt")} />
      ) : result.rows.length === 0 ? (
        <Muted text={t("reports.noData")} />
      ) : (
        <table className="w-full text-sm border-collapse">
          <tbody>
            {result.rows.map((r, i) => (
              <tr key={i} className={`border-b border-solid divide-soft ${r.is_total ? "font-semibold" : ""}`}>
                <td className="py-2 pr-4" style={{ paddingLeft: r.indent * 16 }}>{r.account}</td>
                <td className="py-2 text-right font-semibold num">{xaf(r.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TrialBalancePreview({ token, company, fiscalYear }: { token: string; company: string; fiscalYear: string }) {
  const { t } = useI18n();
  const [result, setResult] = useState<TrialBalanceResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = useMutation({
    mutationFn: () => getTrialBalance(token, { company, fiscal_year: fiscalYear || undefined }),
    onSuccess: (r) => { setError(null); setResult(r); },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });
  return (
    <div>
      <button type="button" onClick={() => run.mutate()} disabled={run.isPending || !company} className="btn btn-outlined mb-4">
        {run.isPending ? t("reports.generating") : result ? t("reports.refreshPreview") : t("reports.loadPreview")}
      </button>
      {error && <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px] mb-3">{error}</div>}
      {!result ? (
        <Muted text={t("reports.statementPrompt")} />
      ) : result.rows.length === 0 ? (
        <Muted text={t("reports.noData")} />
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr>
              <th className={`${TH} pl-1`}>Account</th>
              <th className={`${TH} !text-right`}>Debit</th>
              <th className={`${TH} !text-right`}>Credit</th>
            </tr>
          </thead>
          <tbody>
            {result.rows.map((r, i) => (
              <tr key={i} className="border-b border-solid divide-soft">
                <td className="py-2 pl-1 font-medium">{r.account}</td>
                <td className="py-2 text-right num muted">{r.debit ? xaf(r.debit) : "—"}</td>
                <td className="py-2 text-right num muted">{r.credit ? xaf(r.credit) : "—"}</td>
              </tr>
            ))}
            <tr className="border-t-2 border-divider font-semibold">
              <td className="py-2.5 pl-1">Total</td>
              <td className="py-2.5 text-right num">{xaf(result.total_debit)}</td>
              <td className="py-2.5 text-right num">{xaf(result.total_credit)}</td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}

function CashFlowPreview({ token, company, fiscalYear }: { token: string; company: string; fiscalYear: string }) {
  const { t } = useI18n();
  const [result, setResult] = useState<CashFlowResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = useMutation({
    mutationFn: () => getCashFlow(token, { company: company || undefined, fiscal_year: fiscalYear || undefined }),
    onSuccess: (r) => { setError(null); setResult(r); },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });
  const line = (label: string, value: number, bold = false) => (
    <tr className={`border-b border-solid divide-soft ${bold ? "font-semibold" : ""}`}>
      <td className="py-2 pl-1">{label}</td>
      <td className="py-2 text-right num">{xaf(value)}</td>
    </tr>
  );
  return (
    <div>
      <button type="button" onClick={() => run.mutate()} disabled={run.isPending} className="btn btn-outlined mb-4">
        {run.isPending ? t("reports.generating") : result ? t("reports.refreshPreview") : t("reports.loadPreview")}
      </button>
      {error && <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px] mb-3">{error}</div>}
      {!result ? (
        <Muted text={t("reports.statementPrompt")} />
      ) : (
        <table className="w-full text-sm border-collapse">
          <tbody>
            {line(t("finance.cf.opening"), result.opening, true)}
            {line(t("finance.cf.totalReceived"), result.total_in, true)}
            {line(t("finance.cf.totalPaid"), result.total_out, true)}
            {line(t("finance.cf.net"), result.net_change, true)}
            {line(t("finance.cf.closing"), result.closing, true)}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Table({ head, rows, rightCols = [], emphasizeRight = false }: { head: string[]; rows: string[][]; rightCols?: number[]; emphasizeRight?: boolean }) {
  return (
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr>
          {head.map((h, i) => (
            <th key={i} className={`${TH} ${i === 0 ? "pl-1" : ""} ${rightCols.includes(i) ? "!text-right" : ""}`}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, ri) => (
          <tr key={ri} className="border-b border-solid divide-soft">
            {row.map((cell, ci) => (
              <td
                key={ci}
                className={`py-2.5 ${ci === 0 ? "pl-1 font-medium" : "muted"} ${rightCols.includes(ci) ? `text-right !text-ink font-semibold num ${emphasizeRight ? "!text-warn" : ""}` : ""}`}
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Muted({ text }: { text: string }) {
  return <div className="py-8 text-center muted-2 text-sm">{text}</div>;
}
