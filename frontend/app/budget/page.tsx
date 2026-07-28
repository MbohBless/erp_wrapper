"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import { Icon } from "@/components/icons";
import { UnauthorizedError, compact, groupNum, parseNum, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  ACCOUNT_GROUPS,
  type BudgetReport,
  getBudget,
  saveBudget,
} from "@/lib/budget";

const CELL = "eq-field w-full px-2 py-1.5 text-[13px] !rounded-lg num text-right";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const z12 = <T,>(fill: T): T[] => Array(12).fill(fill);

type Row = { category: string; account_prefix: string; months: string[] };

export default function BudgetPage() {
  return (
    <AppShell>
      <BudgetContent />
    </AppShell>
  );
}

function BudgetContent() {
  const { token, logout } = useAuth();
  const [fiscalYear, setFiscalYear] = useState(String(new Date().getFullYear()));
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, error: qErr } = useQuery({
    queryKey: ["budget", fiscalYear],
    queryFn: () => getBudget(token as string, fiscalYear),
    enabled: !!token,
  });
  useEffect(() => { if (qErr instanceof UnauthorizedError) logout(); }, [qErr, logout]);

  useEffect(() => {
    if (data) {
      setRows(
        data.lines.length
          ? data.lines.map((l) => ({ category: l.category, account_prefix: l.account_prefix, months: l.months_budget.map((m) => (m ? groupNum(String(m)) : "")) }))
          : [{ category: "Revenue", account_prefix: "70", months: z12("") }]
      );
    }
  }, [data?.fiscal_year]); // eslint-disable-line react-hooks/exhaustive-deps

  const actualLine = (prefix: string) => data?.lines.find((l) => l.account_prefix === prefix);

  const save = useMutation({
    mutationFn: (): Promise<BudgetReport> =>
      saveBudget(token as string, {
        fiscal_year: fiscalYear,
        lines: rows.filter((r) => r.category.trim()).map((r) => ({
          category: r.category.trim(), account_prefix: r.account_prefix, months: r.months.map(parseNum),
        })),
      }),
    onSuccess: (r) => {
      setError(null);
      setRows(r.lines.map((l) => ({ category: l.category, account_prefix: l.account_prefix, months: l.months_budget.map((m) => (m ? groupNum(String(m)) : "")) })));
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not save budget"),
  });

  const set = (i: number, patch: Partial<Row>) => setRows((rs) => rs.map((r, x) => (x === i ? { ...r, ...patch } : r)));
  const setMonth = (i: number, m: number, v: string) => setRows((rs) => rs.map((r, x) => (x === i ? { ...r, months: r.months.map((mm, y) => (y === m ? v : mm)) } : r)));
  const spread = (i: number) => setRows((rs) => rs.map((r, x) => (x === i ? { ...r, months: z12(r.months.find((m) => parseNum(m) > 0) || "") } : r)));

  const monthTotals = useMemo(() => {
    const b = z12(0), a = z12(0);
    for (const r of rows) {
      const al = actualLine(r.account_prefix);
      for (let m = 0; m < 12; m++) { b[m] += parseNum(r.months[m]); if (al) a[m] += al.months_actual[m] ?? 0; }
    }
    return { b, a };
  }, [rows, data]);
  const yearBudget = monthTotals.b.reduce((s, x) => s + x, 0);
  const yearActual = monthTotals.a.reduce((s, x) => s + x, 0);

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3"><span>EquiMed</span><span>›</span><span className="text-ink">Budget</span></nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-5">
        <div>
          <h1 className="text-[32px] mb-1">Budget</h1>
          <p className="muted text-sm m-0">Monthly targets tracked against actuals</p>
        </div>
        <div className="flex items-end gap-2.5">
          <div>
            <label className="block text-[12.5px] muted mb-1.5">Fiscal year</label>
            <input className="eq-field num w-28 px-3 py-2.5 text-sm" value={fiscalYear} onChange={(e) => setFiscalYear(e.target.value)} />
          </div>
          <button type="button" onClick={() => { setError(null); save.mutate(); }} disabled={save.isPending} className="btn btn-filled">
            {save.isPending ? "Saving…" : "Save budget"}
          </button>
        </div>
      </div>

      {error && <div className="mb-4 text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px]">{error}</div>}

      <div className="blueprint p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="text-sm border-collapse" style={{ minWidth: 1180 }}>
            <thead>
              <tr className="muted">
                <th className="text-left text-[11px] uppercase font-semibold py-3 pl-5 pr-3 border-b border-divider sticky left-0 bg-bg z-10">Category</th>
                <th className="text-left text-[11px] uppercase font-semibold py-3 pr-3 border-b border-divider">Group</th>
                {MONTHS.map((m) => <th key={m} className="text-right text-[11px] uppercase font-semibold py-3 px-1.5 border-b border-divider w-[78px]">{m}</th>)}
                <th className="text-right text-[11px] uppercase font-semibold py-3 px-3 border-b border-divider">Year</th>
                <th className="border-b border-divider w-10"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={16} className="py-10 text-center muted">Loading…</td></tr>
              ) : (
                rows.map((r, i) => {
                  const al = actualLine(r.account_prefix);
                  const income = r.account_prefix.startsWith("7");
                  const yb = r.months.reduce((s, m) => s + parseNum(m), 0);
                  const ya = al ? al.months_actual.reduce((s, x) => s + x, 0) : null;
                  const pct = yb && ya != null ? Math.round((ya / yb) * 100) : null;
                  const over = pct != null && pct > 100;
                  const barTone = income ? (pct != null && pct >= 100 ? "bg-ok" : "bg-accent") : (over ? "bg-err" : "bg-ok");
                  return (
                    <tr key={i} className="group border-b border-solid divide-soft align-top">
                      <td className="pl-4 py-2 pr-3 sticky left-0 bg-bg group-hover:bg-bg z-10">
                        <input className="eq-field w-[150px] px-2.5 py-1.5 text-[13px] !rounded-lg" value={r.category} onChange={(e) => set(i, { category: e.target.value })} placeholder="Category" />
                        <button type="button" onClick={() => spread(i)} title="Copy the first month across all 12" className="mt-1 text-[11px] text-accent inline-flex items-center gap-1"><Icon name="arrowUp" size={10} sw={2} />Fill across</button>
                      </td>
                      <td className="py-2 pr-3">
                        <select className="eq-field w-[150px] px-2.5 py-1.5 text-[13px] !rounded-lg" value={r.account_prefix} onChange={(e) => set(i, { account_prefix: e.target.value })}>
                          {ACCOUNT_GROUPS.map((g) => <option key={g.prefix} value={g.prefix}>{g.label}</option>)}
                        </select>
                      </td>
                      {r.months.map((m, mi) => {
                        const act = al?.months_actual[mi] ?? null;
                        return (
                          <td key={mi} className="py-2 px-1">
                            <input className={CELL} value={m} onChange={(e) => setMonth(i, mi, groupNum(e.target.value))} placeholder="0" />
                            <div className="text-[10.5px] muted-2 num text-right mt-0.5 h-3">{act ? compact(act) : ""}</div>
                          </td>
                        );
                      })}
                      <td className="py-2 px-3 text-right">
                        <div className="font-semibold num">{xaf(yb)}</div>
                        {ya != null && (
                          <>
                            <div className="text-[11px] muted num">act {compact(ya)}</div>
                            {pct != null && (
                              <div className="flex items-center gap-1.5 mt-1 justify-end">
                                <div className="w-14 h-1.5 rounded-full bg-[color-mix(in_srgb,var(--color-text)_10%,transparent)] overflow-hidden"><div className={`h-full rounded-full ${barTone}`} style={{ width: `${Math.min(pct, 100)}%` }} /></div>
                                <span className={`text-[11px] num ${over ? "text-err font-semibold" : "muted"}`}>{pct}%</span>
                              </div>
                            )}
                          </>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-center">
                        <button type="button" onClick={() => setRows(rows.length > 1 ? rows.filter((_, x) => x !== i) : rows)} className="icobtn grid place-items-center w-7 h-7 muted hover:text-err opacity-0 group-hover:opacity-100"><Icon name="trash" size={14} /></button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
            {!isLoading && (
              <tfoot>
                <tr className="font-semibold border-t-2 border-t-divider">
                  <td className="pl-5 py-3 sticky left-0 bg-bg z-10">Total</td>
                  <td></td>
                  {monthTotals.b.map((b, m) => (
                    <td key={m} className="py-3 px-1.5 text-right num text-[12px]">{b ? compact(b) : "—"}</td>
                  ))}
                  <td className="py-3 px-3 text-right num">{xaf(yearBudget)}<div className="text-[11px] muted font-normal">act {compact(yearActual)}</div></td>
                  <td></td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
        <div className="px-5 py-3 border-t border-divider">
          <button type="button" onClick={() => setRows([...rows, { category: "", account_prefix: "65", months: z12("") }])} className="text-[13px] text-accent inline-flex items-center gap-1"><Icon name="plus" size={13} sw={2} /> Add category</button>
        </div>
      </div>
      <p className="text-xs muted-2 mt-3">Enter a target per month (or fill one across all 12). Actuals are read live from the ledger per month — income categories count credits, expenses count debits. Save to refresh actuals for new rows.</p>
    </div>
  );
}
