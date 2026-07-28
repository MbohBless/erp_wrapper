"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import { Icon } from "@/components/icons";
import { groupNum, parseNum, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { listCustomers } from "@/lib/customers";
import { listProducts } from "@/lib/products";
import { type SalesInvoiceInput, createSale } from "@/lib/sales";

const FIELD = "eq-field w-full px-3 py-2.5 text-sm";
const LABEL = "block text-[13px] muted mb-1.5";
const CELL = "eq-field w-full px-2.5 py-2 text-sm !rounded-lg";

type Tab = "details" | "items" | "more";
type Row = { item_code: string; qty: string; rate: string; description: string };
const emptyRow = (): Row => ({ item_code: "", qty: "1", rate: "", description: "" });

export default function NewInvoicePage() {
  return (
    <AppShell>
      <NewInvoiceForm />
    </AppShell>
  );
}

function NewInvoiceForm() {
  const { t } = useI18n();
  const { token } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("details");

  const [customer, setCustomer] = useState("");
  const [postingDate, setPostingDate] = useState(new Date().toISOString().slice(0, 10));
  const [dueDate, setDueDate] = useState("");
  const [updateStock, setUpdateStock] = useState(false);
  const [remarks, setRemarks] = useState("");
  const [taxTemplate, setTaxTemplate] = useState("");
  const [rows, setRows] = useState<Row[]>([emptyRow()]);
  const [error, setError] = useState<string | null>(null);

  const customersQ = useQuery({ queryKey: ["customers", "", ""], queryFn: () => listCustomers(token as string) });
  const productsQ = useQuery({ queryKey: ["products", ""], queryFn: () => listProducts(token as string) });
  const products = productsQ.data ?? [];

  const setRow = (i: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const addRow = () => setRows((rs) => [...rs, emptyRow()]);
  const removeRow = (i: number) => setRows((rs) => (rs.length > 1 ? rs.filter((_, idx) => idx !== i) : rs));

  function pickItem(i: number, sku: string) {
    const p = products.find((x) => x.id === sku);
    setRow(i, { item_code: sku, rate: p?.selling_price != null ? groupNum(String(p.selling_price)) : "" });
  }

  const totals = useMemo(() => {
    let qty = 0, amount = 0;
    for (const r of rows) {
      const q = parseFloat(r.qty) || 0, rt = parseNum(r.rate) || 0;
      qty += q; amount += q * rt;
    }
    return { qty, amount };
  }, [rows]);

  const save = useMutation({
    mutationFn: () => {
      const input: SalesInvoiceInput = {
        customer,
        posting_date: postingDate || null,
        due_date: dueDate || null,
        remarks: remarks || null,
        update_stock: updateStock,
        taxes_and_charges: taxTemplate || null,
        items: rows
          .filter((r) => r.item_code.trim())
          .map((r) => ({
            item_code: r.item_code.trim(),
            qty: parseFloat(r.qty) || 0,
            rate: parseNum(r.rate) || 0,
            description: r.description || null,
          })),
      };
      return createSale(token as string, input);
    },
    onSuccess: () => router.push("/sales"),
    onError: (e) => setError(e instanceof Error ? e.message : t("sales.err.save")),
  });

  function onSave() {
    setError(null);
    if (!customer) { setError(t("sales.err.customer")); setTab("details"); return; }
    if (!rows.some((r) => r.item_code.trim())) { setError(t("sales.err.items")); setTab("items"); return; }
    save.mutate();
  }

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
              <span>{t("sales.title")}</span><span>›</span><span className="text-ink">{t("sales.new.title")}</span>
            </nav>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-heading font-semibold">{t("sales.new.title")}</h1>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-[color-mix(in_srgb,var(--warn-raw)_16%,transparent)] text-warn">{t("common.notSaved")}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <button type="button" onClick={() => router.push("/sales")} className="btn btn-text">{t("action.cancel")}</button>
          <button type="button" onClick={onSave} disabled={save.isPending} className="btn btn-filled">
            {save.isPending ? t("action.saving") : t("action.save")}
          </button>
        </div>
      </div>

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
              <input className={`${FIELD} opacity-70`} value="ACC-SINV-.YYYY.-" disabled />
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
              <select className={FIELD} value={customer} onChange={(e) => setCustomer(e.target.value)} required>
                <option value="">{t("sales.selectCustomer")}</option>
                {(customersQ.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className={LABEL}>{t("sales.paymentDueDate")}</label>
              <input className={FIELD} type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </div>
          </div>
        )}

        {/* Items */}
        {tab === "items" && (
          <div className="p-6">
            <div className="text-[11px] tracking-[0.08em] uppercase muted mb-3">{t("sales.items")}</div>
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
                            {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
                          </select>
                        </td>
                        <td className="px-2 py-2">
                          <input className={`${CELL} text-right`} type="number" min="0" step="any" value={r.qty} onChange={(e) => setRow(i, { qty: e.target.value })} />
                        </td>
                        <td className="px-2 py-2">
                          <input className={`${CELL} text-right`} inputMode="numeric" value={r.rate} onChange={(e) => setRow(i, { rate: groupNum(e.target.value) })} />
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
