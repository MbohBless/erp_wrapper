"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import { UnauthorizedError, shortDate, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useAppName } from "@/lib/branding";
import { useCompanyName } from "@/lib/company";
import {
  type BookResult,
  type CashFlowResult,
  type FinanceSummary,
  type LedgerResult,
  type OutstandingItem,
  type StatementResult,
  type TrialBalanceResult,
  getBalanceSheet,
  getBankBook,
  getCashBook,
  getCashFlow,
  getFinanceSummary,
  getIncomeStatement,
  getPayable,
  getReceivable,
  getTrialBalance,
} from "@/lib/finance";

type Tab =
  | "summary"
  | "receivables"
  | "payables"
  | "cash"
  | "bank"
  | "trial"
  | "cashflow"
  | "statements";
const TABS: { key: Tab; labelKey: string }[] = [
  { key: "summary", labelKey: "finance.tab.summary" },
  { key: "receivables", labelKey: "finance.tab.receivables" },
  { key: "payables", labelKey: "finance.tab.payables" },
  { key: "cash", labelKey: "finance.tab.cash" },
  { key: "bank", labelKey: "finance.tab.bank" },
  { key: "trial", labelKey: "finance.tab.trial" },
  { key: "cashflow", labelKey: "finance.tab.cashflow" },
  { key: "statements", labelKey: "finance.tab.statements" },
];

export default function FinancePage() {
  return (
    <AppShell>
      <FinanceContent />
    </AppShell>
  );
}

function FinanceContent() {
  const appName = useAppName();
  const { token, logout } = useAuth();
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("summary");

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>{appName}</span>
        <span>›</span>
        <span className="text-ink">{t("finance.title")}</span>
      </nav>
      <div className="mb-5">
        <h1 className="text-[32px] mb-1">{t("finance.title")}</h1>
        <p className="muted text-sm m-0">
          {t("finance.subtitle")}
        </p>
      </div>

      <div className="flex items-center gap-1 border-b border-divider mb-5 overflow-x-auto eq-scroll">
        {TABS.map((tb) => (
          <button
            key={tb.key}
            type="button"
            onClick={() => setTab(tb.key)}
            className={`relative px-4 py-2.5 text-sm font-heading font-semibold -mb-px whitespace-nowrap ${
              tab === tb.key ? "text-ink" : "muted hover:text-ink"
            }`}
          >
            {t(tb.labelKey)}
            {tab === tb.key && (
              <span className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />
            )}
          </button>
        ))}
      </div>

      {tab === "summary" && <SummaryTab token={token} onAuthError={logout} />}
      {tab === "receivables" && <LedgerTab token={token} kind="receivable" onAuthError={logout} />}
      {tab === "payables" && <LedgerTab token={token} kind="payable" onAuthError={logout} />}
      {tab === "cash" && <BookTab token={token} kind="cash" onAuthError={logout} />}
      {tab === "bank" && <BookTab token={token} kind="bank" onAuthError={logout} />}
      {tab === "trial" && <TrialBalanceTab token={token} />}
      {tab === "cashflow" && <CashFlowTab token={token} />}
      {tab === "statements" && <StatementsTab token={token} />}
    </div>
  );
}

function useAuthGuard(error: unknown, onAuthError: () => void) {
  useEffect(() => {
    if (error instanceof UnauthorizedError) onAuthError();
  }, [error, onAuthError]);
}

// -------------------------------------------------------------- Summary
function SummaryTab({ token, onAuthError }: { token: string | null; onAuthError: () => void }) {
  const { t } = useI18n();
  const { data, isLoading, error } = useQuery({
    queryKey: ["finance-summary"],
    queryFn: () => getFinanceSummary(token as string),
    enabled: !!token,
  });
  useAuthGuard(error, onAuthError);
  if (isLoading) return <Loading />;
  if (!data) return <ErrorCard />;
  const d: FinanceSummary = data;
  const netOk = d.net_position >= 0;
  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
        <StatCard label={t("finance.receivables")} value={xaf(d.receivables)} />
        <StatCard label={t("finance.payables")} value={xaf(d.payables)} />
        <StatCard label={t("finance.netPosition")} value={`${netOk ? "+" : ""}${xaf(d.net_position)}`} valueClass={netOk ? "text-ok" : "text-err"} />
        <StatCard label={t("finance.overdue")} value={xaf(d.overdue_receivables)} valueClass="text-err" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <OutstandingTable title={t("finance.outstandingReceivables")} party={t("finance.party.customer")} rows={d.outstanding_receivables} />
        <OutstandingTable title={t("finance.outstandingPayables")} party={t("finance.party.supplier")} rows={d.outstanding_payables} />
      </div>
    </>
  );
}

function OutstandingTable({ title, party, rows }: { title: string; party: string; rows: OutstandingItem[] }) {
  const { t } = useI18n();
  return (
    <Blueprint className="p-0 overflow-hidden">
      <div className="px-5 py-4 border-b border-divider font-heading font-semibold text-base">{title}</div>
      {rows.length === 0 ? (
        <div className="py-12 text-center muted-2 text-sm">{t("finance.nothingOutstanding")}</div>
      ) : (
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="muted">
              <Th className="pl-5">{party}</Th><Th>{t("finance.col.due")}</Th><Th className="!text-right pr-5">{t("finance.col.amount")}</Th>
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

// ------------------------------------------------------- AR / AP ledger
function LedgerTab({ token, kind, onAuthError }: { token: string | null; kind: "receivable" | "payable"; onAuthError: () => void }) {
  const { t } = useI18n();
  const { data, isLoading, error } = useQuery({
    queryKey: ["ledger", kind],
    queryFn: () => (kind === "receivable" ? getReceivable(token as string) : getPayable(token as string)),
    enabled: !!token,
  });
  useAuthGuard(error, onAuthError);
  if (isLoading) return <Loading />;
  if (!data) return <ErrorCard />;
  const d: LedgerResult = data;
  const party = kind === "receivable" ? t("finance.party.customer") : t("finance.party.supplier");
  const buckets: [string, number][] = [
    [t("finance.bucket.current"), d.totals.current], ["1-30", d.totals.d30], ["31-60", d.totals.d60],
    ["61-90", d.totals.d90], ["90+", d.totals.older], [t("finance.bucket.total"), d.totals.total],
  ];
  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3 mb-4">
        {buckets.map(([label, val], i) => (
          <StatCard key={label} label={label} value={xaf(val)} small valueClass={i === 5 ? "text-accent" : i === 4 ? "text-err" : ""} />
        ))}
      </div>
      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[820px]">
            <thead>
              <tr className="muted">
                <Th className="pl-5">{party}</Th><Th>{t("finance.col.reference")}</Th><Th>{t("finance.col.posting")}</Th><Th>{t("finance.col.due")}</Th>
                <Th className="!text-right">{t("finance.col.age")}</Th><Th>{t("finance.col.bucket")}</Th><Th className="!text-right pr-5">{t("finance.col.outstanding")}</Th>
              </tr>
            </thead>
            <tbody>
              {d.rows.length === 0 ? (
                <tr><td colSpan={7} className="py-12 text-center muted-2">{t("finance.nothingOutstanding")}</td></tr>
              ) : (
                d.rows.map((r) => (
                  <tr key={r.reference} className="border-b border-solid divide-soft">
                    <td className="pl-5 py-3 font-medium">{r.party}</td>
                    <td className="py-3 muted font-heading tracking-wide">{r.reference}</td>
                    <td className="py-3 muted">{shortDate(r.posting_date)}</td>
                    <td className="py-3 muted">{shortDate(r.due_date)}</td>
                    <td className="py-3 text-right muted">{r.age_days}d</td>
                    <td className="py-3"><Bucket b={r.bucket} /></td>
                    <td className="px-5 py-3 text-right font-semibold">{xaf(r.outstanding)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Blueprint>
    </>
  );
}

function Bucket({ b }: { b: string }) {
  const { t } = useI18n();
  const cls = b === "Current" ? "text-ok" : b === "90+" ? "text-err" : b === "61-90" ? "text-warn" : "muted";
  const label = b === "Current" ? t("finance.bucket.current") : b;
  return <span className={`text-[13px] ${cls}`}>{label}</span>;
}

// ------------------------------------------------------- Cash / Bank book
function BookTab({ token, kind, onAuthError }: { token: string | null; kind: "cash" | "bank"; onAuthError: () => void }) {
  const { t } = useI18n();
  const { data, isLoading, error } = useQuery({
    queryKey: ["book", kind],
    queryFn: () => (kind === "cash" ? getCashBook(token as string) : getBankBook(token as string)),
    enabled: !!token,
  });
  useAuthGuard(error, onAuthError);
  if (isLoading) return <Loading />;
  if (!data) return <ErrorCard />;
  const d: BookResult = data;
  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <StatCard label={t("finance.opening")} value={xaf(d.opening)} small />
        <StatCard label={t("finance.debitIn")} value={xaf(d.total_debit)} small valueClass="text-ok" />
        <StatCard label={t("finance.creditOut")} value={xaf(d.total_credit)} small valueClass="text-err" />
        <StatCard label={t("finance.closing")} value={xaf(d.closing)} small valueClass="text-accent" />
      </div>
      {d.accounts.length > 0 && (
        <p className="text-xs muted mb-3">{t("finance.accounts")}: {d.accounts.join(" · ")}</p>
      )}
      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[880px]">
            <thead>
              <tr className="muted">
                <Th className="pl-5">{t("finance.col.date")}</Th><Th>{t("finance.col.voucher")}</Th><Th>{t("finance.col.party")}</Th><Th>{t("finance.col.against")}</Th>
                <Th className="!text-right">{t("finance.col.debit")}</Th><Th className="!text-right">{t("finance.col.credit")}</Th><Th className="!text-right pr-5">{t("finance.col.balance")}</Th>
              </tr>
            </thead>
            <tbody>
              {d.entries.length === 0 ? (
                <tr><td colSpan={7} className="py-12 text-center muted-2">{kind === "cash" ? t("finance.noCashTx") : t("finance.noBankTx")}</td></tr>
              ) : (
                d.entries.map((e, i) => (
                  <tr key={i} className="border-b border-solid divide-soft">
                    <td className="pl-5 py-2.5 muted">{shortDate(e.date)}</td>
                    <td className="py-2.5 font-heading tracking-wide text-[13px]">{e.voucher_no}</td>
                    <td className="py-2.5 muted">{e.party ?? "—"}</td>
                    <td className="py-2.5 muted">{e.against ?? "—"}</td>
                    <td className="py-2.5 text-right">{e.debit ? xaf(e.debit) : "—"}</td>
                    <td className="py-2.5 text-right">{e.credit ? xaf(e.credit) : "—"}</td>
                    <td className="px-5 py-2.5 text-right font-semibold">{xaf(e.balance)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Blueprint>
    </>
  );
}

// --------------------------------------------------------- Trial balance
function useCompanyYear() {
  const defaultCompany = useCompanyName();
  const [company, setCompany] = useState("");
  useEffect(() => {
    setCompany((c) => c || defaultCompany);
  }, [defaultCompany]);
  const [year, setYear] = useState(String(new Date().getFullYear()));
  return { company, setCompany, year, setYear };
}

function QueryControls({
  company, setCompany, year, setYear, busy, onRun,
}: {
  company: string; setCompany: (v: string) => void;
  year: string; setYear: (v: string) => void;
  busy: boolean; onRun: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-end gap-2.5 mb-5">
      <div>
        <label className="block text-[13px] muted mb-2">{t("finance.company")}</label>
        <input className="eq-field px-4 py-3 text-[15px]" value={company} onChange={(e) => setCompany(e.target.value)} />
      </div>
      <div className="w-28">
        <label className="block text-[13px] muted mb-2">{t("finance.fiscalYear")}</label>
        <input className="eq-field w-full px-4 py-3 text-[15px]" value={year} onChange={(e) => setYear(e.target.value)} />
      </div>
      <button type="button" onClick={onRun} disabled={busy || !company} className="btn btn-filled">
        {busy ? t("finance.running") : t("finance.generate")}
      </button>
    </div>
  );
}

function TrialBalanceTab({ token }: { token: string | null }) {
  const { t } = useI18n();
  const { company, setCompany, year, setYear } = useCompanyYear();
  const [result, setResult] = useState<TrialBalanceResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!token || !company) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await getTrialBalance(token, { company, fiscal_year: year || undefined }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("finance.failed"));
    } finally {
      setBusy(false);
    }
  }

  const balanced = result ? Math.round(result.total_debit - result.total_credit) === 0 : true;

  return (
    <div>
      <QueryControls company={company} setCompany={setCompany} year={year} setYear={setYear} busy={busy} onRun={run} />
      {error && <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px] mb-4">{error}</div>}
      {!result ? (
        <div className="blueprint p-10 text-center muted-2 text-sm">{t("finance.chooseStatement")}</div>
      ) : result.rows.length === 0 ? (
        <div className="blueprint p-10 text-center muted-2 text-sm">{t("finance.noData")}</div>
      ) : (
        <Blueprint className="p-0 overflow-hidden">
          <div className="overflow-x-auto eq-scroll">
            <table className="w-full text-sm border-collapse min-w-[560px]">
              <thead>
                <tr className="muted">
                  <Th className="pl-5">{t("finance.col.account")}</Th>
                  <Th className="!text-right">{t("finance.col.debit")}</Th>
                  <Th className="!text-right pr-5">{t("finance.col.credit")}</Th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r, i) => (
                  <tr key={i} className="border-b border-solid divide-soft">
                    <td className="pl-5 py-2.5 font-medium">{r.account}</td>
                    <td className="py-2.5 text-right num">{r.debit ? xaf(r.debit) : "—"}</td>
                    <td className="px-5 py-2.5 text-right num">{r.credit ? xaf(r.credit) : "—"}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-divider font-semibold">
                  <td className="pl-5 py-3">{t("finance.bucket.total")}</td>
                  <td className="py-3 text-right num">{xaf(result.total_debit)}</td>
                  <td className="px-5 py-3 text-right num">{xaf(result.total_credit)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Blueprint>
      )}
      {result && (
        <p className={`mt-3 text-[13px] ${balanced ? "text-ok" : "text-err"}`}>
          {balanced ? t("finance.tb.balanced") : t("finance.tb.unbalanced")}
        </p>
      )}
    </div>
  );
}

// --------------------------------------------------------- Cash flow
function CashFlowTab({ token }: { token: string | null }) {
  const { t } = useI18n();
  const { company, setCompany, year, setYear } = useCompanyYear();
  const [result, setResult] = useState<CashFlowResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await getCashFlow(token, { company: company || undefined, fiscal_year: year || undefined }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("finance.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <QueryControls company={company} setCompany={setCompany} year={year} setYear={setYear} busy={busy} onRun={run} />
      {error && <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px] mb-4">{error}</div>}
      {!result ? (
        <div className="blueprint p-10 text-center muted-2 text-sm">{t("finance.chooseStatement")}</div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <StatCard label={t("finance.cf.opening")} value={xaf(result.opening)} small />
            <StatCard label={t("finance.cf.totalReceived")} value={xaf(result.total_in)} small valueClass="text-ok" />
            <StatCard label={t("finance.cf.totalPaid")} value={xaf(result.total_out)} small valueClass="text-err" />
            <StatCard label={t("finance.cf.closing")} value={xaf(result.closing)} small valueClass="text-accent" />
          </div>
          <Blueprint className="p-0 overflow-hidden">
            <table className="w-full text-sm border-collapse">
              <tbody>
                <CfRow label={t("finance.cf.opening")} value={xaf(result.opening)} bold />
                <CfSection label={t("finance.cf.received")} />
                {result.inflows.length === 0 ? (
                  <CfRow label={t("finance.cf.none")} value="—" indent muted />
                ) : (
                  result.inflows.map((l, i) => <CfRow key={`i${i}`} label={l.label} value={xaf(l.amount)} indent />)
                )}
                <CfRow label={t("finance.cf.totalReceived")} value={xaf(result.total_in)} bold />
                <CfSection label={t("finance.cf.paid")} />
                {result.outflows.length === 0 ? (
                  <CfRow label={t("finance.cf.none")} value="—" indent muted />
                ) : (
                  result.outflows.map((l, i) => <CfRow key={`o${i}`} label={l.label} value={xaf(l.amount)} indent />)
                )}
                <CfRow label={t("finance.cf.totalPaid")} value={xaf(result.total_out)} bold />
                <CfRow label={t("finance.cf.net")} value={xaf(result.net_change)} bold valueClass={result.net_change >= 0 ? "text-ok" : "text-err"} />
                <CfRow label={t("finance.cf.closing")} value={xaf(result.closing)} bold valueClass="text-accent" />
              </tbody>
            </table>
          </Blueprint>
        </>
      )}
    </div>
  );
}

function CfSection({ label }: { label: string }) {
  return (
    <tr className="border-b border-solid divide-soft bg-[color-mix(in_srgb,var(--color-text)_3%,transparent)]">
      <td colSpan={2} className="px-5 py-2 text-[11px] tracking-[0.1em] uppercase muted font-semibold">{label}</td>
    </tr>
  );
}

function CfRow({ label, value, bold, indent, muted, valueClass }: {
  label: string; value: string; bold?: boolean; indent?: boolean; muted?: boolean; valueClass?: string;
}) {
  return (
    <tr className={`border-b border-solid divide-soft ${bold ? "font-semibold" : ""}`}>
      <td className={`py-2.5 ${indent ? "pl-10" : "pl-5"} ${muted ? "muted-2" : ""}`}>{label}</td>
      <td className={`px-5 py-2.5 text-right num ${valueClass ?? ""}`}>{value}</td>
    </tr>
  );
}

// --------------------------------------------------------- Statements
function StatementsTab({ token }: { token: string | null }) {
  const { t } = useI18n();
  const [which, setWhich] = useState<"income-statement" | "balance-sheet">("income-statement");
  const defaultCompany = useCompanyName();
  const [company, setCompany] = useState("");
  useEffect(() => {
    setCompany((c) => c || defaultCompany);
  }, [defaultCompany]);
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [result, setResult] = useState<StatementResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!token || !company) return;
    setBusy(true);
    setError(null);
    try {
      const fn = which === "income-statement" ? getIncomeStatement : getBalanceSheet;
      setResult(await fn(token, { company, fiscal_year: year || undefined }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("finance.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end gap-2.5 mb-5">
        <div>
          <label className="block text-[13px] muted mb-2">{t("finance.statement")}</label>
          <select className="eq-field px-4 py-3 text-[15px]" value={which} onChange={(e) => setWhich(e.target.value as typeof which)}>
            <option value="income-statement">{t("finance.incomeStatement")}</option>
            <option value="balance-sheet">{t("finance.balanceSheet")}</option>
          </select>
        </div>
        <div>
          <label className="block text-[13px] muted mb-2">{t("finance.company")}</label>
          <input className="eq-field px-4 py-3 text-[15px]" value={company} onChange={(e) => setCompany(e.target.value)} />
        </div>
        <div className="w-28">
          <label className="block text-[13px] muted mb-2">{t("finance.fiscalYear")}</label>
          <input className="eq-field w-full px-4 py-3 text-[15px]" value={year} onChange={(e) => setYear(e.target.value)} />
        </div>
        <button type="button" onClick={run} disabled={busy || !company} className="btn btn-filled">
          {busy ? t("finance.running") : t("finance.generate")}
        </button>
      </div>

      {error && <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px] mb-4">{error}</div>}

      {!result ? (
        <div className="blueprint p-10 text-center muted-2 text-sm">{t("finance.chooseStatement")}</div>
      ) : result.rows.length === 0 ? (
        <div className="blueprint p-10 text-center muted-2 text-sm">{t("finance.noData")}</div>
      ) : (
        <Blueprint className="p-0 overflow-hidden">
          <div className="px-5 py-4 border-b border-divider font-heading font-semibold text-base">{result.title}</div>
          <table className="w-full text-sm border-collapse">
            <tbody>
              {result.rows.map((r, i) => (
                <tr key={i} className={`border-b border-solid divide-soft ${r.is_total ? "font-semibold" : ""}`}>
                  <td className="py-2.5 pr-4" style={{ paddingLeft: 20 + r.indent * 18 }}>{r.account}</td>
                  <td className="px-5 py-2.5 text-right font-semibold num">{xaf(r.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Blueprint>
      )}
    </div>
  );
}

// --------------------------------------------------------------- shared
function StatCard({ label, value, valueClass, small }: { label: string; value: string; valueClass?: string; small?: boolean }) {
  return (
    <Blueprint className="p-4">
      <div className="text-[11px] tracking-[0.1em] uppercase muted">{label}</div>
      <div className={`font-heading font-semibold ${small ? "text-[18px]" : "text-[26px]"} mt-1 ${valueClass ?? ""}`}>{value}</div>
    </Blueprint>
  );
}

function Th({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return <th className={`text-left text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${className}`}>{children}</th>;
}

function Loading() {
  return (
    <div className="animate-pulse">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="blueprint h-[92px]" />)}</div>
      <div className="blueprint h-[280px]" />
    </div>
  );
}
function ErrorCard() {
  const { t } = useI18n();
  return <div className="blueprint p-10 text-center muted">{t("finance.loadError")}</div>;
}
