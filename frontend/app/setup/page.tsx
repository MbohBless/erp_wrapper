"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import { Icon } from "@/components/icons";
import { groupNum, parseNum, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { listCustomers } from "@/lib/customers";
import { listSuppliers } from "@/lib/suppliers";
import { useAppName } from "@/lib/branding";
import {
  type BudgetItem,
  type LoanItem,
  type OpeningItem,
  getSetupStatus,
  postOpeningBalances,
} from "@/lib/setup";

const FIELD = "eq-field w-full px-3 py-2.5 text-sm";
const LABEL = "block text-[13px] muted mb-1.5";
const CELL = "eq-field w-full px-2.5 py-2 text-sm !rounded-lg";

const STEPS = [
  "Start date", "Bank & cash", "Receivables", "Payables", "Inventory",
  "Equipment", "Loans", "Owner's equity", "Budget", "Review & post",
];

type ARRow = { party: string; reference: string; due_date: string; amount: string };
type LoanRow = { lender: string; kind: string; amount: string; rate: string; end_date: string };
type BudRow = { category: string; yearly: string };

const emptyAR = (): ARRow => ({ party: "", reference: "", due_date: "", amount: "" });
const emptyLoan = (): LoanRow => ({ lender: "", kind: "took", amount: "", rate: "", end_date: "" });

export default function SetupPage() {
  return (
    <AppShell>
      <SetupWizard />
    </AppShell>
  );
}

function SetupWizard() {
  const appName = useAppName();
  const { token } = useAuth();
  const router = useRouter();

  const statusQ = useQuery({ queryKey: ["setup-status"], queryFn: () => getSetupStatus(token as string), enabled: !!token });
  const customersQ = useQuery({ queryKey: ["customers", "", ""], queryFn: () => listCustomers(token as string), enabled: !!token });
  const suppliersQ = useQuery({ queryKey: ["suppliers", "", ""], queryFn: () => listSuppliers(token as string), enabled: !!token });

  const [step, setStep] = useState(0);
  const [startDate, setStartDate] = useState("2026-01-01");
  const [bank, setBank] = useState("");
  const [cash, setCash] = useState("");
  const [inv, setInv] = useState("");
  const [equip, setEquip] = useState("");
  const [ar, setAR] = useState<ARRow[]>([emptyAR()]);
  const [ap, setAP] = useState<ARRow[]>([emptyAR()]);
  const [loans, setLoans] = useState<LoanRow[]>([emptyLoan()]);
  const [budgets, setBudgets] = useState<BudRow[]>([
    { category: "Revenue", yearly: "" },
    { category: "Purchases (COGS)", yearly: "" },
    { category: "Salaries", yearly: "" },
    { category: "Rent & utilities", yearly: "" },
  ]);
  const [error, setError] = useState<string | null>(null);

  const t = useMemo(() => {
    const arTotal = ar.reduce((s, r) => s + parseNum(r.amount), 0);
    const apTotal = ap.reduce((s, r) => s + parseNum(r.amount), 0);
    const loanTotal = loans.filter((l) => l.kind !== "gave").reduce((s, l) => s + parseNum(l.amount), 0);
    const assets = parseNum(bank) + parseNum(cash) + parseNum(inv) + parseNum(equip) + arTotal;
    const liab = apTotal + loanTotal;
    return { arTotal, apTotal, loanTotal, assets, liab, equity: assets - liab };
  }, [ar, ap, loans, bank, cash, inv, equip]);

  const post = useMutation({
    mutationFn: () =>
      postOpeningBalances(token as string, {
        start_date: startDate,
        bank: parseNum(bank), cash: parseNum(cash),
        inventory_value: parseNum(inv), equipment_value: parseNum(equip),
        receivables: ar.filter((r) => r.party && parseNum(r.amount) > 0)
          .map((r): OpeningItem => ({ party: r.party, reference: r.reference || null, due_date: r.due_date || null, date: startDate, amount: parseNum(r.amount) })),
        payables: ap.filter((r) => r.party && parseNum(r.amount) > 0)
          .map((r): OpeningItem => ({ party: r.party, reference: r.reference || null, due_date: r.due_date || null, date: startDate, amount: parseNum(r.amount) })),
        loans: loans.filter((l) => parseNum(l.amount) > 0)
          .map((l): LoanItem => ({ lender: l.lender, kind: l.kind, amount: parseNum(l.amount), rate: l.rate ? parseNum(l.rate) : null, end_date: l.end_date || null })),
        budgets: budgets.filter((b) => parseNum(b.yearly) > 0)
          .map((b): BudgetItem => ({ category: b.category, yearly: parseNum(b.yearly) })),
      }),
    onSuccess: () => router.push("/dashboard"),
    onError: (e) => setError(e instanceof Error ? e.message : "Could not post opening balances"),
  });

  if (statusQ.data?.setup_complete) {
    return (
      <div className="eq-view max-w-2xl">
        <div className="blueprint p-8 text-center">
          <div className="w-12 h-12 rounded-full grid place-items-center mx-auto mb-4 bg-[color-mix(in_srgb,var(--ok-raw)_18%,transparent)] text-ok">
            <Icon name="check" size={24} sw={2.2} />
          </div>
          <h1 className="text-2xl font-heading font-semibold mb-1">Your books are set up</h1>
          <p className="muted text-sm mb-1">Opening balances were posted as of {statusQ.data.start_date}.</p>
          <p className="muted-2 text-xs mb-6">Reference: {statusQ.data.opening_ref}</p>
          <button className="btn btn-filled" onClick={() => router.push("/dashboard")}>Go to dashboard</button>
        </div>
      </div>
    );
  }

  const asOf = new Date(startDate + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  const last = STEPS.length - 1;

  return (
    <div className="eq-view">
      <div className="flex items-center justify-between gap-4 mb-5 flex-wrap">
        <div>
          <nav className="flex items-center gap-2 text-xs muted mb-1"><span>{appName}</span><span>›</span><span className="text-ink">Set up your books</span></nav>
          <h1 className="text-[30px] font-heading font-semibold leading-tight">Set up your books</h1>
        </div>
        <div className="inline-flex items-center gap-2 text-[12.5px] font-medium px-3 py-1.5 rounded-full bg-[color-mix(in_srgb,var(--color-accent)_12%,transparent)] text-accent">
          <span className="w-1.5 h-1.5 rounded-full bg-accent" />Balances as of <b className="num">{asOf}</b>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[240px_1fr] gap-6 items-start">
        {/* stepper */}
        <nav className="rounded-2xl border border-divider bg-bg p-2.5 hidden md:block">
          {STEPS.map((s, i) => (
            <button key={s} type="button" onClick={() => setStep(i)}
              className={`relative w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm ${i === step ? "bg-[color-mix(in_srgb,var(--color-accent)_12%,transparent)] font-semibold text-ink" : "muted hover:text-ink"}`}>
              {i === step && <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded bg-accent" />}
              <span className={`w-[22px] h-[22px] rounded-full grid place-items-center text-[11px] font-semibold shrink-0 num ${i < step ? "bg-accent text-bg" : i === step ? "border-[1.5px] border-accent text-accent" : "border-[1.5px] border-divider muted"}`}>{i < step ? "✓" : i + 1}</span>
              <span className="leading-tight">{s}</span>
              {i === 8 && <span className="ml-auto text-[10px] uppercase tracking-wide muted-3">Optional</span>}
            </button>
          ))}
        </nav>

        {/* panel */}
        <div className="blueprint bg-bg p-0 overflow-hidden flex flex-col min-h-[440px]">
          <div className="p-7 flex-1">
            <div className="text-[11px] tracking-[0.1em] uppercase muted-3 mb-1"><span className="text-accent font-semibold">Step {step + 1}</span> · {step === 8 ? "Optional" : "of " + STEPS.length}</div>

            {step === 0 && (
              <StepShell title={`When should ${appName} start keeping your books?`} lead={`Pick the day your finances are reconciled and up to date — your cut-over date. We record your balances as of this day; everything after it, ${appName} tracks for you.`}>
                <div className="max-w-[260px]"><label className={LABEL}>Start date</label>
                  <input className={`${FIELD} num`} type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></div>
              </StepShell>
            )}

            {step === 1 && (
              <StepShell title="How much cash do you have on the start date?" lead={`The balance in each account and your till as of ${asOf}.`}>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 max-w-xl">
                  <MoneyField label="Bank — main account" value={bank} onChange={setBank} />
                  <MoneyField label="Cash / till" value={cash} onChange={setCash} />
                </div>
              </StepShell>
            )}

            {step === 2 && (
              <ItemStep title="Money customers owe you" lead={`Add each unpaid customer invoice separately, so ${appName} can chase payment and age it correctly.`}
                rows={ar} setRows={setAR} parties={(customersQ.data ?? []).map((c) => ({ id: c.id, name: c.name }))} partyLabel="Customer" refLabel="Invoice #" addLabel="Add invoice" />
            )}
            {step === 3 && (
              <ItemStep title="Money you owe suppliers" lead="Add each unpaid supplier bill separately, so you can pay it off and track what's due."
                rows={ap} setRows={setAP} parties={(suppliersQ.data ?? []).map((s) => ({ id: s.id, name: s.name }))} partyLabel="Supplier" refLabel="Bill #" addLabel="Add bill" />
            )}

            {step === 4 && (
              <StepShell title="What stock do you have on hand?" lead="Enter the total value of stock on the start date — you can refine per product later from Inventory.">
                <div className="max-w-[280px]"><MoneyField label="Total stock value" value={inv} onChange={setInv} /></div>
              </StepShell>
            )}
            {step === 5 && (
              <StepShell title="Equipment & other assets" lead="The value of equipment and assets the business owns on the start date — vehicles, fridges, IT.">
                <div className="max-w-[280px]"><MoneyField label="Total equipment & assets value" value={equip} onChange={setEquip} /></div>
              </StepShell>
            )}

            {step === 6 && (
              <StepShell title="Loans & debts" lead="Add each loan the business has — money you borrowed, or lent out — with the balance still owed on the start date.">
                <div className="flex flex-col gap-3">
                  {loans.map((l, i) => (
                    <div key={i} className="rounded-xl border border-divider p-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div><label className={LABEL}>Lender / borrower</label><input className={FIELD} value={l.lender} onChange={(e) => setLoans(up(loans, i, { lender: e.target.value }))} /></div>
                      <div><label className={LABEL}>Type</label>
                        <select className={FIELD} value={l.kind} onChange={(e) => setLoans(up(loans, i, { kind: e.target.value }))}>
                          <option value="took">Loan we took</option><option value="gave">Loan we gave</option></select></div>
                      <div><label className={LABEL}>Balance owed (as of start)</label><input className={`${FIELD} num text-right`} value={l.amount} onChange={(e) => setLoans(up(loans, i, { amount: groupNum(e.target.value) }))} placeholder="0" /></div>
                      <div><label className={LABEL}>Interest rate (%/yr)</label><input className={`${FIELD} num`} value={l.rate} onChange={(e) => setLoans(up(loans, i, { rate: e.target.value }))} /></div>
                      <div><label className={LABEL}>End date</label><input className={`${FIELD} num`} type="date" value={l.end_date} onChange={(e) => setLoans(up(loans, i, { end_date: e.target.value }))} /></div>
                      <div className="flex items-end"><button type="button" className="btn btn-text text-err" onClick={() => setLoans(loans.length > 1 ? loans.filter((_, x) => x !== i) : loans)}>Remove</button></div>
                    </div>
                  ))}
                  <button type="button" className="text-[13px] text-accent inline-flex items-center gap-1 self-start" onClick={() => setLoans([...loans, emptyLoan()])}><Icon name="plus" size={13} sw={2} /> Add another loan</button>
                </div>
              </StepShell>
            )}

            {step === 7 && (
              <StepShell title="Owner's equity" lead={`This is what the owners have put into the business. ${appName} works it out so the books balance — what you own minus what you owe.`}>
                <div className="rounded-xl border border-divider p-5 max-w-md">
                  <Row k="What you own (assets)" v={xaf(t.assets)} />
                  <Row k="What you owe (liabilities)" v={"− " + xaf(t.liab)} />
                  <div className="flex items-baseline justify-between pt-3 mt-1 border-t border-solid divide-soft">
                    <div><div className="font-semibold">Opening equity</div><div className="text-[11px] muted-2">Calculated automatically · adjustable with your accountant</div></div>
                    <div className="text-xl font-heading font-semibold num text-accent">{xaf(t.equity)}</div>
                  </div>
                </div>
              </StepShell>
            )}

            {step === 8 && (
              <StepShell title="Set a budget" lead={`Optional. Give ${appName} a yearly target per category and reports can show plan vs actual. Skip it and set budgets any time.`}>
                <div className="overflow-x-auto eq-scroll border border-divider rounded-xl max-w-xl">
                  <table className="w-full text-sm border-collapse">
                    <thead><tr className="muted bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
                      <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5">Category</th>
                      <th className="text-right text-[11px] uppercase font-semibold px-3 py-2.5">Yearly target</th></tr></thead>
                    <tbody>{budgets.map((b, i) => (
                      <tr key={i} className="border-t border-divider">
                        <td className="px-2 py-1.5"><input className={CELL} value={b.category} onChange={(e) => setBudgets(up(budgets, i, { category: e.target.value }))} /></td>
                        <td className="px-2 py-1.5"><input className={`${CELL} num text-right`} value={b.yearly} onChange={(e) => setBudgets(up(budgets, i, { yearly: groupNum(e.target.value) }))} placeholder="0" /></td>
                      </tr>))}</tbody>
                  </table>
                </div>
                <button type="button" className="text-[13px] text-accent inline-flex items-center gap-1 mt-3" onClick={() => setBudgets([...budgets, { category: "", yearly: "" }])}><Icon name="plus" size={13} sw={2} /> Add category</button>
              </StepShell>
            )}

            {step === 9 && (
              <StepShell title="Your opening snapshot" lead={`Where your books stand on ${asOf}. Post it once and ${appName} takes over from here.`}>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="rounded-xl border border-divider p-4 bg-[color-mix(in_srgb,var(--color-text)_2%,transparent)]">
                    <div className="text-[11px] uppercase tracking-wide muted font-semibold mb-2">What you own</div>
                    <Row k="Bank — main account" v={xaf(parseNum(bank))} /><Row k="Cash / till" v={xaf(parseNum(cash))} />
                    <Row k="Customers owe you" v={xaf(t.arTotal)} /><Row k="Stock on hand" v={xaf(parseNum(inv))} />
                    <Row k="Equipment & assets" v={xaf(parseNum(equip))} />
                    <Row k="Total assets" v={xaf(t.assets)} strong />
                  </div>
                  <div className="rounded-xl border border-divider p-4 bg-[color-mix(in_srgb,var(--color-text)_2%,transparent)]">
                    <div className="text-[11px] uppercase tracking-wide muted font-semibold mb-2">What you owe & own</div>
                    <Row k="Suppliers you owe" v={xaf(t.apTotal)} /><Row k="Loans outstanding" v={xaf(t.loanTotal)} />
                    <Row k="Total liabilities" v={xaf(t.liab)} strong />
                    <div className="mt-2"><Row k="Opening equity" v={xaf(t.equity)} /></div>
                    <Row k="Liabilities + equity" v={xaf(t.liab + t.equity)} strong />
                  </div>
                </div>
                <div className="flex items-center justify-between gap-4 flex-wrap mt-5 p-4 rounded-xl bg-[color-mix(in_srgb,var(--ok-raw)_12%,transparent)] border border-[color-mix(in_srgb,var(--ok-raw)_35%,transparent)]">
                  <span className="inline-flex items-center gap-2 text-ok font-semibold"><Icon name="check" size={18} sw={2.4} /> Balanced — assets equal liabilities plus equity</span>
                  <button type="button" className="btn btn-filled !bg-ok" disabled={post.isPending} onClick={() => { setError(null); post.mutate(); }}>{post.isPending ? "Posting…" : "Post opening balances"}</button>
                </div>
                <p className="text-xs muted-2 mt-2">Posting writes these figures to the ledger once. You can still edit them from Settings afterwards.</p>
              </StepShell>
            )}

            {error && <div className="mt-5 text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px]">{error}</div>}
          </div>

          <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-divider bg-[color-mix(in_srgb,var(--color-text)_2%,transparent)]">
            <div className="text-[12.5px] muted">Step <b className="text-ink num">{step + 1}</b> of <b className="num">{STEPS.length}</b></div>
            <div className="flex gap-2.5">
              <button type="button" className="btn btn-text" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
              {step < last
                ? <button type="button" className="btn btn-filled" onClick={() => setStep(step + 1)}>{step === 7 ? "Continue" : "Continue"}</button>
                : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---- helpers & sub-components ----
function up<T>(rows: T[], i: number, patch: Partial<T>): T[] {
  return rows.map((r, x) => (x === i ? { ...r, ...patch } : r));
}
function StepShell({ title, lead, children }: { title: string; lead: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-[22px] font-heading font-semibold mt-1 mb-2">{title}</h2>
      <p className="muted text-sm max-w-[62ch] mb-6">{lead}</p>
      {children}
    </div>
  );
}
function MoneyField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div><label className={LABEL}>{label}</label>
      <div className="relative"><input className={`${FIELD} num text-right pr-14`} value={value} onChange={(e) => onChange(groupNum(e.target.value))} placeholder="0" />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs muted-2">FCFA</span></div></div>
  );
}
function Row({ k, v, strong }: { k: string; v: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between py-1.5 text-sm ${strong ? "font-semibold border-t border-solid divide-soft mt-1 pt-2.5" : "border-b border-dashed divide-soft"}`}>
      <span className={strong ? "" : "muted"}>{k}</span><span className="num">{v}</span></div>
  );
}
function ItemStep({ title, lead, rows, setRows, parties, partyLabel, refLabel, addLabel }: {
  title: string; lead: string; rows: ARRow[]; setRows: (r: ARRow[]) => void;
  parties: { id: string; name: string }[]; partyLabel: string; refLabel: string; addLabel: string;
}) {
  const total = rows.reduce((s, r) => s + parseNum(r.amount), 0);
  return (
    <StepShell title={title} lead={lead}>
      <div className="overflow-x-auto eq-scroll border border-divider rounded-xl">
        <table className="w-full text-sm border-collapse min-w-[640px]">
          <thead><tr className="muted bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
            <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5">{partyLabel}</th>
            <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5 w-32">{refLabel}</th>
            <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5 w-40">Due date</th>
            <th className="text-right text-[11px] uppercase font-semibold px-3 py-2.5 w-36">Amount</th>
            <th className="w-10" /></tr></thead>
          <tbody>{rows.map((r, i) => (
            <tr key={i} className="border-t border-divider">
              <td className="px-2 py-1.5"><select className={CELL} value={r.party} onChange={(e) => setRows(up(rows, i, { party: e.target.value }))}>
                <option value="">Select…</option>{parties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></td>
              <td className="px-2 py-1.5"><input className={CELL} value={r.reference} onChange={(e) => setRows(up(rows, i, { reference: e.target.value }))} placeholder="Ref" /></td>
              <td className="px-2 py-1.5"><input className={`${CELL} num`} type="date" value={r.due_date} onChange={(e) => setRows(up(rows, i, { due_date: e.target.value }))} /></td>
              <td className="px-2 py-1.5"><input className={`${CELL} num text-right`} value={r.amount} onChange={(e) => setRows(up(rows, i, { amount: groupNum(e.target.value) }))} placeholder="0" /></td>
              <td className="px-2 py-1.5 text-center"><button type="button" className="icobtn grid place-items-center w-7 h-7 muted hover:text-err" onClick={() => setRows(rows.length > 1 ? rows.filter((_, x) => x !== i) : rows)}><Icon name="trash" size={14} /></button></td>
            </tr>))}</tbody>
        </table>
      </div>
      <div className="flex items-center justify-between mt-3">
        <button type="button" className="text-[13px] text-accent inline-flex items-center gap-1" onClick={() => setRows([...rows, emptyAR()])}><Icon name="plus" size={13} sw={2} /> {addLabel}</button>
        <span className="text-[13px] muted">Total <b className="text-ink num ml-1.5">{xaf(total)}</b></span>
      </div>
    </StepShell>
  );
}
