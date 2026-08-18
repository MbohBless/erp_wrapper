"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Icon } from "@/components/icons";
import { groupNum, parseNum, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { listProducts } from "@/lib/products";
import { listSuppliers } from "@/lib/suppliers";
import {
  type PurchaseInput,
  type PurchaseInvoice,
  createPurchase,
  updatePurchase,
} from "@/lib/purchases";

const FIELD = "eq-field w-full px-3 py-2.5 text-sm";
const LABEL = "block text-[13px] muted mb-1.5";
const CELL = "eq-field w-full px-2.5 py-2 text-sm !rounded-lg";

type Tab = "details" | "items" | "more";
type Row = { item_code: string; qty: string; rate: string };
const emptyRow = (): Row => ({ item_code: "", qty: "1", rate: "" });

const today = () => new Date().toISOString().slice(0, 10);

function rowsFrom(bill?: PurchaseInvoice): Row[] {
  if (!bill || bill.items.length === 0) return [emptyRow()];
  return bill.items.map((line) => ({
    item_code: line.item_code,
    qty: String(line.qty),
    rate: groupNum(String(line.rate)),
  }));
}

/**
 * One form for entering a supplier bill and for correcting a posted one.
 *
 * See `components/sales/InvoiceForm.tsx` — same cancel-then-amend semantics,
 * same reason every field is seeded from the original.
 */
export default function BillForm({ amending }: { amending?: PurchaseInvoice }) {
  const { t } = useI18n();
  const { token } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("details");

  const [supplier, setSupplier] = useState(amending?.supplier ?? "");
  const [postingDate, setPostingDate] = useState(amending?.posting_date ?? today());
  const [billNo, setBillNo] = useState(amending?.bill_no ?? "");
  const [remarks, setRemarks] = useState(amending?.remarks ?? "");
  const [rows, setRows] = useState<Row[]>(() => rowsFrom(amending));
  const [error, setError] = useState<string | null>(null);
  const [posted, setPosted] = useState<string | null>(null);

  const suppliersQ = useQuery({ queryKey: ["suppliers", "", ""], queryFn: () => listSuppliers(token as string) });
  const productsQ = useQuery({ queryKey: ["products", ""], queryFn: () => listProducts(token as string) });
  const products = productsQ.data ?? [];

  const setRow = (i: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const addRow = () => setRows((rs) => [...rs, emptyRow()]);
  const removeRow = (i: number) => setRows((rs) => (rs.length > 1 ? rs.filter((_, idx) => idx !== i) : rs));

  function pickItem(i: number, sku: string) {
    const p = products.find((x) => x.id === sku);
    setRow(i, { item_code: sku, rate: p?.purchase_price != null ? groupNum(String(p.purchase_price)) : "" });
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
      const input: PurchaseInput = {
        supplier,
        posting_date: postingDate || null,
        bill_no: billNo || null,
        remarks: remarks || null,
        items: rows
          .filter((r) => r.item_code.trim())
          .map((r) => ({ item_code: r.item_code.trim(), qty: parseFloat(r.qty) || 0, rate: parseNum(r.rate) || 0 })),
      };
      return amending
        ? updatePurchase(token as string, amending.id, input)
        : createPurchase(token as string, input);
    },
    onSuccess: (bill) => {
      if (amending) setPosted(bill.id);
      else router.push("/purchases");
    },
    onError: (e) => setError(e instanceof Error ? e.message : t("purchases.err.save")),
  });

  function onSave() {
    setError(null);
    if (!supplier) { setError(t("purchases.err.supplier")); setTab("details"); return; }
    if (!rows.some((r) => r.item_code.trim())) { setError(t("purchases.err.items")); setTab("items"); return; }
    save.mutate();
  }

  if (posted && amending) {
    return (
      <div className="eq-view -mt-1">
        <div className="blueprint bg-bg p-8 max-w-xl">
          <h1 className="text-2xl font-heading font-semibold mb-2">
            {t("purchases.amend.doneTitle")}
          </h1>
          <p className="muted text-sm mb-5">
            {t("purchases.amend.doneBody")
              .replace("{old}", amending.id)
              .replace("{new}", posted)}
          </p>
          <button type="button" onClick={() => router.push("/purchases")} className="btn btn-filled">
            {t("purchases.amend.backToList")}
          </button>
        </div>
      </div>
    );
  }

  const title = amending ? t("purchases.amend.title") : t("purchases.new.title");

  return (
    <div className="eq-view -mt-1">
      <div className="flex items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <button onClick={() => router.push("/purchases")} className="icobtn grid place-items-center w-9 h-9 border border-divider muted" title={t("action.back")}>
            <Icon name="chevronDown" size={18} />
          </button>
          <div className="min-w-0">
            <nav className="flex items-center gap-2 text-xs muted">
              <span>{t("purchases.title")}</span><span>›</span><span className="text-ink">{amending?.id ?? title}</span>
            </nav>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-heading font-semibold">{title}</h1>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-[color-mix(in_srgb,var(--warn-raw)_16%,transparent)] text-warn">{t("common.notSaved")}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <button type="button" onClick={() => router.push("/purchases")} className="btn btn-text">{t("action.cancel")}</button>
          <button type="button" onClick={onSave} disabled={save.isPending} className="btn btn-filled">
            {save.isPending ? t("action.saving") : amending ? t("purchases.amend.post") : t("action.save")}
          </button>
        </div>
      </div>

      {amending && (
        <div className="blueprint p-4 mb-4 text-[13px] flex gap-3 items-start">
          <span className="text-warn shrink-0 mt-0.5"><Icon name="alert" size={16} /></span>
          <p className="m-0">{t("purchases.amend.notice").replace("{id}", amending.id)}</p>
        </div>
      )}

      <div className="blueprint bg-bg p-0 overflow-hidden">
        <div className="flex items-center gap-1 border-b border-divider px-4">
          {(["details", "items", "more"] as Tab[]).map((tb) => (
            <button key={tb} type="button" onClick={() => setTab(tb)}
              className={`relative px-4 py-3 text-sm font-heading font-semibold -mb-px capitalize ${tab === tb ? "text-ink" : "muted hover:text-ink"}`}>
              {tb === "more" ? t("common.moreInfo") : tb === "items" ? t("purchases.tab.items") : t("common.details")}
              {tab === tb && <span className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />}
            </button>
          ))}
        </div>

        {error && (
          <div className="mx-6 mt-5 text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px]">{error}</div>
        )}

        {tab === "details" && (
          <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-5">
            <div>
              <label className={LABEL}>{t("purchases.series")}</label>
              <input className={`${FIELD} opacity-70`} value={amending ? `${amending.id}-…` : "ACC-PINV-.YYYY.-"} disabled />
            </div>
            <div>
              <label className={LABEL}>{t("purchases.postingDate")}</label>
              <input className={FIELD} type="date" value={postingDate} onChange={(e) => setPostingDate(e.target.value)} />
            </div>
            <div>
              <label className={LABEL}>{t("purchases.supplierBillNo")}</label>
              <input className={FIELD} value={billNo} onChange={(e) => setBillNo(e.target.value)} placeholder={t("purchases.supplierBillPlaceholder")} />
            </div>
            <div>
              <label className={LABEL}>{t("purchases.supplier")} *</label>
              <select className={FIELD} value={supplier} onChange={(e) => setSupplier(e.target.value)} required>
                <option value="">{t("purchases.selectSupplier")}</option>
                {(suppliersQ.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          </div>
        )}

        {tab === "items" && (
          <div className="p-6">
            <div className="text-[11px] tracking-[0.08em] uppercase muted mb-3">{t("purchases.items")}</div>
            <div className="overflow-x-auto eq-scroll border border-divider rounded-xl">
              <table className="w-full text-sm border-collapse min-w-[720px]">
                <thead>
                  <tr className="muted bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
                    <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5 w-10">{t("purchases.col.no")}</th>
                    <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5">{t("purchases.col.item")}</th>
                    <th className="text-right text-[11px] uppercase font-semibold px-3 py-2.5 w-24">{t("purchases.col.quantity")}</th>
                    <th className="text-right text-[11px] uppercase font-semibold px-3 py-2.5 w-36">{t("purchases.col.rateXaf")}</th>
                    <th className="text-right text-[11px] uppercase font-semibold px-3 py-2.5 w-40">{t("purchases.col.amountXaf")}</th>
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
                            <option value="">{t("purchases.selectItem")}</option>
                            {/* Keep a line whose item has since left the catalogue selectable,
                                so re-posting a corrected bill does not drop it. */}
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
                          <input className={`${CELL} text-right`} inputMode="numeric" value={r.rate} onChange={(e) => setRow(i, { rate: groupNum(e.target.value) })} />
                        </td>
                        <td className="px-3 py-2 text-right font-medium num">{xaf(amount)}</td>
                        <td className="px-2 py-2 text-center">
                          <button type="button" onClick={() => removeRow(i)} className="icobtn grid place-items-center w-7 h-7 muted hover:text-err" title={t("purchases.remove")}>
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
              <Icon name="plus" size={13} sw={2} /> {t("purchases.addRow")}
            </button>

            <div className="flex flex-wrap justify-end gap-x-10 gap-y-2 mt-5 pt-4 border-t border-divider">
              <div className="text-right">
                <div className="text-[11px] uppercase muted">{t("purchases.totalQuantity")}</div>
                <div className="font-heading font-semibold text-lg num">{totals.qty}</div>
              </div>
              <div className="text-right">
                <div className="text-[11px] uppercase muted">{t("purchases.totalXaf")}</div>
                <div className="font-heading font-semibold text-lg num">{xaf(totals.amount)}</div>
              </div>
            </div>
          </div>
        )}

        {tab === "more" && (
          <div className="p-6">
            <label className={LABEL}>{t("purchases.remarks")}</label>
            <textarea className={`${FIELD} min-h-[90px] resize-y max-w-2xl`} value={remarks} onChange={(e) => setRemarks(e.target.value)} />
          </div>
        )}
      </div>
    </div>
  );
}
