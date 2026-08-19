"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Icon } from "@/components/icons";
import { groupNum, parseNum, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import Combobox from "@/components/ui/Combobox";
import { useDebounced } from "@/components/ui/hooks";
import { listCustomers } from "@/lib/customers";
import { listProducts } from "@/lib/products";
import {
  type SalesInvoice,
  type SalesInvoiceInput,
  createSale,
  updateSale,
} from "@/lib/sales";

const FIELD = "eq-field w-full px-3 py-2.5 text-sm";
const LABEL = "block text-[13px] muted mb-1.5";
const CELL = "eq-field w-full px-2.5 py-2 text-sm !rounded-lg";

type Tab = "details" | "items" | "more";
type Row = { item_code: string; qty: string; rate: string; description: string };
const emptyRow = (): Row => ({ item_code: "", qty: "1", rate: "", description: "" });

const today = () => new Date().toISOString().slice(0, 10);

/** The item grid, seeded from an invoice being corrected. */
function rowsFrom(invoice?: SalesInvoice): Row[] {
  if (!invoice || invoice.items.length === 0) return [emptyRow()];
  return invoice.items.map((line) => ({
    item_code: line.item_code,
    qty: String(line.qty),
    rate: groupNum(String(line.rate)),
    description: "",
  }));
}

/**
 * One form for raising an invoice and for correcting a posted one.
 *
 * With `amending` set it is a correction, and the difference is not cosmetic:
 * saving cancels that invoice and posts a replacement under a *new number*.
 * Every field therefore has to be seeded from the original — a PUT replaces the
 * whole document, so a tax template or stock flag left out of the payload is
 * written as empty rather than kept.
 */
export default function InvoiceForm({ amending }: { amending?: SalesInvoice }) {
  const { t } = useI18n();
  const { token } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("details");

  const [customer, setCustomer] = useState(amending?.customer ?? "");
  const [postingDate, setPostingDate] = useState(amending?.posting_date ?? today());
  const [dueDate, setDueDate] = useState(amending?.due_date ?? "");
  const [updateStock, setUpdateStock] = useState(amending?.update_stock ?? false);
  const [remarks, setRemarks] = useState(amending?.remarks ?? "");
  const [taxTemplate, setTaxTemplate] = useState(amending?.taxes_and_charges ?? "");
  const [commissioned, setCommissioned] = useState(amending?.is_commissioned ?? false);
  const [agent, setAgent] = useState(amending?.commission_agent ?? "");
  const [rows, setRows] = useState<Row[]>(() => rowsFrom(amending));
  const [error, setError] = useState<string | null>(null);
  // The replacement's id, once it exists. Shown rather than navigated past:
  // the number changing is the one thing about an amendment a user must see.
  const [posted, setPosted] = useState<string | null>(null);

  // Searches ERPNext as the user types rather than loading a fixed slice
  // of the master list. Loaded whole the list is capped, and past the cap
  // a record is simply unselectable with nothing on screen to say why.
  const customerSearch = useDebounced(customer);
  const customersQ = useQuery({
    queryKey: ["customers", "picker", customerSearch],
    queryFn: () =>
      listCustomers(token as string, { search: customerSearch || undefined, limit: 20 }),
    enabled: !!token,
  });
  // The item picker still loads a slice of the catalogue rather than
  // searching it. Explicit rather than relying on the default, so the
  // ceiling is visible in the code: past this many products a SKU would
  // be unselectable here. Fine at a catalogue of tens; revisit at
  // hundreds, when this needs the same treatment as the party picker.
  const productsQ = useQuery({
    queryKey: ["products", "picker"],
    queryFn: () => listProducts(token as string, { limit: 500 }),
  });
  const products = productsQ.data ?? [];

  const setRow = (i: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const addRow = () => setRows((rs) => [...rs, emptyRow()]);
  const removeRow = (i: number) => setRows((rs) => (rs.length > 1 ? rs.filter((_, idx) => idx !== i) : rs));

  function pickItem(i: number, sku: string) {
    const p = products.find((x) => x.id === sku);
    setRow(i, { item_code: sku, rate: p?.selling_price != null ? groupNum(String(p.selling_price)) : "" });
  }

  /** A row's list price, straight from the catalogue — the same figure the
   *  server will stamp on the line, so what is shown here is what gets
   *  recorded. Undefined for a product with no price on file. */
  const listRate = (code: string) =>
    products.find((p) => p.id === code)?.selling_price ?? undefined;

  /**
   * Unticking has to put the prices back.
   *
   * Otherwise the flag is trivially defeated: tick it, drop the rate, untick
   * it, and the invoice goes out below list with no reason recorded anywhere —
   * exactly the hole the lock exists to close.
   */
  function toggleCommissioned(next: boolean) {
    setCommissioned(next);
    if (next) return;
    setAgent("");
    setRows((rs) =>
      rs.map((r) => {
        const list = listRate(r.item_code);
        return list != null ? { ...r, rate: groupNum(String(list)) } : r;
      })
    );
  }

  const totals = useMemo(() => {
    let qty = 0, amount = 0, given = 0;
    for (const r of rows) {
      const q = parseFloat(r.qty) || 0, rt = parseNum(r.rate) || 0;
      qty += q; amount += q * rt;
      const list = listRate(r.item_code);
      if (list != null && rt > 0 && list > rt) given += (list - rt) * q;
    }
    return { qty, amount, given };
  }, [rows, products]);

  const save = useMutation({
    mutationFn: () => {
      const input: SalesInvoiceInput = {
        customer,
        posting_date: postingDate || null,
        due_date: dueDate || null,
        remarks: remarks || null,
        update_stock: updateStock,
        taxes_and_charges: taxTemplate || null,
        is_commissioned: commissioned,
        commission_agent: commissioned ? agent.trim() || null : null,
        items: rows
          .filter((r) => r.item_code.trim())
          .map((r) => ({
            item_code: r.item_code.trim(),
            qty: parseFloat(r.qty) || 0,
            rate: parseNum(r.rate) || 0,
            description: r.description || null,
          })),
      };
      return amending
        ? updateSale(token as string, amending.id, input)
        : createSale(token as string, input);
    },
    onSuccess: (invoice) => {
      if (amending) setPosted(invoice.id);
      else router.push("/sales");
    },
    onError: (e) => setError(e instanceof Error ? e.message : t("sales.err.save")),
  });

  function onSave() {
    setError(null);
    if (!customer) { setError(t("sales.err.customer")); setTab("details"); return; }
    // A customer must be one ERPNext knows. Typed free-hand it fails there as
    // an opaque link error, well after the user has stopped looking at it.
    if (!(customersQ.data ?? []).some((c) => c.id === customer)) {
      setError(t("sales.err.customerUnknown").replace("{name}", customer));
      setTab("details");
      return;
    }
    if (!rows.some((r) => r.item_code.trim())) { setError(t("sales.err.items")); setTab("items"); return; }
    if (commissioned && !agent.trim()) { setError(t("sales.err.agent")); setTab("details"); return; }
    save.mutate();
  }

  if (posted && amending) {
    return (
      <div className="eq-view -mt-1">
        <div className="blueprint bg-bg p-8 max-w-xl">
          <h1 className="text-2xl font-heading font-semibold mb-2">
            {t("sales.amend.doneTitle")}
          </h1>
          <p className="muted text-sm mb-5">
            {t("sales.amend.doneBody")
              .replace("{old}", amending.id)
              .replace("{new}", posted)}
          </p>
          <div className="flex items-center gap-2.5">
            <button type="button" onClick={() => router.push("/sales")} className="btn btn-filled">
              {t("sales.amend.backToList")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const title = amending ? t("sales.amend.title") : t("sales.new.title");

  return (
    <div className="eq-view -mt-1">
      {/* ERPNext-style form header */}
      <div className="flex items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <button onClick={() => router.push("/sales")} className="icobtn grid place-items-center w-9 h-9 border border-divider muted" title={t("action.back")}>
            <Icon name="chevronDown" size={18} />
          </button>
          <div className="min-w-0">
            <nav className="flex items-center gap-2 text-xs muted">
              <span>{t("sales.title")}</span><span>›</span><span className="text-ink">{amending?.id ?? title}</span>
            </nav>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-heading font-semibold">{title}</h1>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-[color-mix(in_srgb,var(--warn-raw)_16%,transparent)] text-warn">{t("common.notSaved")}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <button type="button" onClick={() => router.push("/sales")} className="btn btn-text">{t("action.cancel")}</button>
          <button type="button" onClick={onSave} disabled={save.isPending} className="btn btn-filled">
            {save.isPending ? t("action.saving") : amending ? t("sales.amend.post") : t("action.save")}
          </button>
        </div>
      </div>

      {amending && (
        <div className="blueprint p-4 mb-4 text-[13px] flex gap-3 items-start">
          <span className="text-warn shrink-0 mt-0.5"><Icon name="alert" size={16} /></span>
          <p className="m-0">{t("sales.amend.notice").replace("{id}", amending.id)}</p>
        </div>
      )}

      <div className="blueprint bg-bg p-0 overflow-hidden">
        {/* Tabs */}
        <div className="flex items-center gap-1 border-b border-divider px-4">
          {(["details", "items", "more"] as Tab[]).map((tb) => (
            <button key={tb} type="button" onClick={() => setTab(tb)}
              className={`relative px-4 py-3 text-sm font-heading font-semibold -mb-px capitalize ${tab === tb ? "text-ink" : "muted hover:text-ink"}`}>
              {tb === "more" ? t("common.moreInfo") : tb === "items" ? t("sales.tab.items") : t("common.details")}
              {tab === tb && <span className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />}
            </button>
          ))}
        </div>

        {error && (
          <div className="mx-6 mt-5 text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px]">{error}</div>
        )}

        {/* Details */}
        {tab === "details" && (
          <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-5">
            <div>
              <label className={LABEL}>{t("sales.series")}</label>
              <input className={`${FIELD} opacity-70`} value={amending ? `${amending.id}-…` : "ACC-SINV-.YYYY.-"} disabled />
            </div>
            <div>
              <label className={LABEL}>{t("sales.postingDate")}</label>
              <input className={FIELD} type="date" value={postingDate} onChange={(e) => setPostingDate(e.target.value)} />
            </div>
            <label className="flex items-center gap-2.5 text-sm cursor-pointer self-end pb-2.5">
              <input type="checkbox" checked={updateStock} onChange={(e) => setUpdateStock(e.target.checked)} />
              {t("sales.updateStock")}
            </label>
            <div>
              <label className={LABEL}>{t("sales.customer")} *</label>
              <Combobox
                value={customer}
                onChange={setCustomer}
                options={(customersQ.data ?? []).map((c) => ({
                  value: c.id,
                  hint: c.name !== c.id ? c.name : null,
                }))}
                placeholder={t("sales.selectCustomer")}
                emptyHint={t("sales.customerNoMatch")}
                required
              />
            </div>
            <div>
              <label className={LABEL}>{t("sales.paymentDueDate")}</label>
              <input className={FIELD} type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </div>

            {/* A sale brokered by an agent and billed below the catalogue
                price. Ticking the box is what separates a deliberate
                concession from a mistyped rate when someone reads this back. */}
            <div className="md:col-span-3 pt-2 border-t border-divider">
              <label className="flex items-center gap-2.5 text-sm cursor-pointer">
                <input type="checkbox" checked={commissioned}
                  onChange={(e) => toggleCommissioned(e.target.checked)} />
                {t("sales.commissioned")}
              </label>
              <p className="text-xs muted mt-1.5 max-w-xl">{t("sales.commissionedHint")}</p>
              {commissioned && (
                <div className="mt-3 max-w-sm">
                  <label className={LABEL}>{t("sales.commissionAgent")} *</label>
                  <input className={FIELD} value={agent}
                    onChange={(e) => setAgent(e.target.value)}
                    placeholder={t("sales.commissionAgentPlaceholder")} />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Items */}
        {tab === "items" && (
          <div className="p-6">
            <div className="flex items-baseline justify-between gap-4 mb-3">
              <div className="text-[11px] tracking-[0.08em] uppercase muted">{t("sales.items")}</div>
              {!commissioned && (
                <div className="text-xs muted-2">{t("sales.rateLockedHint")}</div>
              )}
            </div>
            <div className="overflow-x-auto eq-scroll border border-divider rounded-xl">
              <table className="w-full text-sm border-collapse min-w-[720px]">
                <thead>
                  <tr className="muted bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
                    <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5 w-10">{t("sales.col.no")}</th>
                    <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5">{t("sales.col.item")}</th>
                    <th className="text-right text-[11px] uppercase font-semibold px-3 py-2.5 w-24">{t("sales.col.quantity")}</th>
                    <th className="text-right text-[11px] uppercase font-semibold px-3 py-2.5 w-36">{t("sales.col.rateXaf")}</th>
                    <th className="text-right text-[11px] uppercase font-semibold px-3 py-2.5 w-40">{t("sales.col.amountXaf")}</th>
                    <th className="w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const amount = (parseFloat(r.qty) || 0) * (parseNum(r.rate) || 0);
                    return (
                      <tr key={i} className="border-t border-divider">
                        <td className="px-3 py-2 muted text-center">{i + 1}</td>
                        <td className="px-2 py-2">
                          <select className={CELL} value={r.item_code} onChange={(e) => pickItem(i, e.target.value)}>
                            <option value="">{t("sales.selectItem")}</option>
                            {/* An amended invoice can reference an item that has since been
                                disabled and dropped out of the catalogue; keep it selectable
                                so re-posting does not silently lose the line. */}
                            {r.item_code && !products.some((p) => p.id === r.item_code) && (
                              <option value={r.item_code}>{r.item_code}</option>
                            )}
                            {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
                          </select>
                        </td>
                        <td className="px-2 py-2">
                          <input className={`${CELL} text-right`} type="number" min="0" step="any" value={r.qty} onChange={(e) => setRow(i, { qty: e.target.value })} />
                        </td>
                        <td className="px-2 py-2">
                          {(() => {
                            const list = listRate(r.item_code);
                            // Locked to the catalogue price unless the sale is
                            // marked commissioned. An item with no price on
                            // file has nothing to lock to, so it stays open —
                            // otherwise it could never be invoiced at all.
                            const locked = !commissioned && list != null;
                            const charged = parseNum(r.rate) || 0;
                            return (
                              <>
                                <input
                                  className={`${CELL} text-right ${locked ? "opacity-60 cursor-not-allowed" : ""}`}
                                  inputMode="numeric"
                                  value={r.rate}
                                  readOnly={locked}
                                  tabIndex={locked ? -1 : undefined}
                                  title={locked ? t("sales.rateLocked") : undefined}
                                  onChange={(e) => setRow(i, { rate: groupNum(e.target.value) })}
                                />
                                {list != null && charged > 0 && list > charged && (
                                  <div className="text-[11px] muted-2 text-right mt-1">
                                    {t("sales.listPrice")} {xaf(list)}
                                  </div>
                                )}
                              </>
                            );
                          })()}
                        </td>
                        <td className="px-3 py-2 text-right font-medium num">{xaf(amount)}</td>
                        <td className="px-2 py-2 text-center">
                          <button type="button" onClick={() => removeRow(i)} className="icobtn grid place-items-center w-7 h-7 muted hover:text-err" title={t("sales.remove")}>
                            <Icon name="trash" size={14} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <button type="button" onClick={addRow} className="mt-3 text-[13px] text-accent inline-flex items-center gap-1">
              <Icon name="plus" size={13} sw={2} /> {t("sales.addRow")}
            </button>

            <div className="flex flex-wrap justify-end gap-x-10 gap-y-2 mt-5 pt-4 border-t border-divider">
              <div className="text-right">
                <div className="text-[11px] uppercase muted">{t("sales.totalQuantity")}</div>
                <div className="font-heading font-semibold text-lg num">{totals.qty}</div>
              </div>
              {totals.given > 0 && (
                <div className="text-right">
                  <div className="text-[11px] uppercase muted">{t("sales.givenAway")}</div>
                  <div className="font-heading font-semibold text-lg num text-warn">
                    {xaf(totals.given)}
                  </div>
                </div>
              )}
              <div className="text-right">
                <div className="text-[11px] uppercase muted">{t("sales.totalXaf")}</div>
                <div className="font-heading font-semibold text-lg num">{xaf(totals.amount)}</div>
              </div>
            </div>
          </div>
        )}

        {/* More info */}
        {tab === "more" && (
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
            <div className="md:col-span-2">
              <label className={LABEL}>{t("sales.taxTemplate")}</label>
              <input className={FIELD} value={taxTemplate} onChange={(e) => setTaxTemplate(e.target.value)} placeholder={t("sales.taxPlaceholder")} />
              <p className="text-xs muted mt-1.5">{t("sales.taxHint")}</p>
            </div>
            <div className="md:col-span-2">
              <label className={LABEL}>{t("sales.remarks")}</label>
              <textarea className={`${FIELD} min-h-[90px] resize-y`} value={remarks} onChange={(e) => setRemarks(e.target.value)} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
