"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import DocFormShell, { DOC_FIELD, DOC_LABEL } from "@/components/ui/DocFormShell";
import { Icon } from "@/components/icons";
import { groupNum, parseNum, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { listProducts } from "@/lib/products";
import {
  type MovementInput,
  issueGoods,
  listBatches,
  listWarehouses,
  receiveGoods,
} from "@/lib/inventory";

type Row = { item_code: string; qty: string; batch_no: string; rate: string };
const emptyRow = (): Row => ({ item_code: "", qty: "1", batch_no: "", rate: "" });
const CELL = "eq-field w-full px-2.5 py-2 text-sm !rounded-lg";

export default function StockEntryPage() {
  const { t } = useI18n();
  return (
    <AppShell>
      <Suspense fallback={<div className="eq-view muted">{t("common.loading")}</div>}>
        <StockEntryForm />
      </Suspense>
    </AppShell>
  );
}

function StockEntryForm() {
  const { token } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const qc = useQueryClient();
  const params = useSearchParams();
  const receiving = params.get("mode") !== "issue";

  const [tab, setTab] = useState("details");
  const [warehouse, setWarehouse] = useState("");
  const [rows, setRows] = useState<Row[]>([emptyRow()]);
  const [error, setError] = useState<string | null>(null);

  const warehousesQ = useQuery({ queryKey: ["warehouses"], queryFn: () => listWarehouses(token as string), enabled: !!token });
  const productsQ = useQuery({ queryKey: ["products", ""], queryFn: () => listProducts(token as string), enabled: !!token });
  const batchesQ = useQuery({ queryKey: ["batches"], queryFn: () => listBatches(token as string), enabled: !!token });
  const products = productsQ.data ?? [];
  const batches = batchesQ.data ?? [];

  const setRow = (i: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const addRow = () => setRows((rs) => [...rs, emptyRow()]);
  const removeRow = (i: number) => setRows((rs) => (rs.length > 1 ? rs.filter((_, idx) => idx !== i) : rs));

  function pickItem(i: number, sku: string) {
    const p = products.find((x) => x.id === sku);
    setRow(i, { item_code: sku, rate: receiving && p?.purchase_price != null ? groupNum(String(p.purchase_price)) : rows[i].rate });
  }

  const totalQty = useMemo(
    () => rows.reduce((s, r) => s + (parseFloat(r.qty) || 0), 0),
    [rows]
  );

  const save = useMutation({
    mutationFn: () => {
      const input: MovementInput = {
        warehouse,
        items: rows
          .filter((r) => r.item_code.trim())
          .map((r) => ({
            item_code: r.item_code.trim(),
            qty: parseFloat(r.qty) || 0,
            batch_no: r.batch_no || null,
            rate: receiving && r.rate ? parseNum(r.rate) : null,
          })),
      };
      return receiving ? receiveGoods(token as string, input) : issueGoods(token as string, input);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stock"] });
      router.push("/inventory");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Could not post stock entry"),
  });

  function onSave() {
    setError(null);
    if (!warehouse) { setError("Select a warehouse."); setTab("details"); return; }
    if (!rows.some((r) => r.item_code.trim())) { setError("Add at least one item."); setTab("items"); return; }
    save.mutate();
  }

  // Group warehouses are structure, not places: ERPNext refuses them for
  // transactions ("Group node warehouse is not allowed to select for
  // transactions"), which reached the user as an unexplained 502. Do not offer
  // what cannot be chosen.
  const warehouses = (warehousesQ.data ?? []).filter((w) => !w.is_group);

  // Preselect where stock actually goes. This is a distribution business —
  // devices arrive finished and leave finished — so Finished Goods is the
  // answer almost every time, and making someone choose it on every movement
  // is a keystroke that only ever has one right value.
  //
  // Only fills an EMPTY field, so a deliberate choice is never overwritten,
  // and falls back to the sole warehouse when there is only one.
  useEffect(() => {
    if (warehouse || warehouses.length === 0) return;
    const preferred =
      warehouses.find((w) => /finished goods/i.test(w.id)) ??
      (warehouses.length === 1 ? warehouses[0] : undefined);
    if (preferred) setWarehouse(preferred.id);
  }, [warehouses, warehouse]);

  return (
    <DocFormShell
      breadcrumb={t("inventory.title")}
      title={receiving ? t("inventory.receiveGoods") : t("inventory.issueGoods")}
      statusLabel={t("common.notSaved")}
      backHref="/inventory"
      tabs={[{ id: "details", label: t("common.details") }, { id: "items", label: t("inventory.items") }]}
      active={tab}
      onTab={setTab}
      onSave={onSave}
      saving={save.isPending}
      saveLabel={receiving ? t("inventory.receive") : t("inventory.issue")}
      error={error}
    >
      {tab === "details" && (
        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-5">
          <div>
            <label className={DOC_LABEL}>{t("inventory.entryType")}</label>
            <input className={`${DOC_FIELD} opacity-70`} value={receiving ? t("inventory.materialReceipt") : t("inventory.materialIssue")} disabled />
          </div>
          <div className="md:col-span-2">
            <label className={DOC_LABEL}>{receiving ? t("inventory.targetWarehouse") : t("inventory.sourceWarehouse")} *</label>
            <select className={DOC_FIELD} value={warehouse} onChange={(e) => setWarehouse(e.target.value)} required>
              <option value="">{t("inventory.selectWarehouse")}</option>
              {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
        </div>
      )}

      {tab === "items" && (
        <div className="p-6">
          <div className="text-[11px] tracking-[0.08em] uppercase muted mb-3">{t("inventory.items")}</div>
          <div className="overflow-x-auto eq-scroll border border-divider rounded-xl">
            <table className="w-full text-sm border-collapse min-w-[720px]">
              <thead>
                <tr className="muted bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
                  <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5 w-10">{t("inventory.colNo")}</th>
                  <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5">{t("inventory.colItem")}</th>
                  <th className="text-right text-[11px] uppercase font-semibold px-3 py-2.5 w-24">{t("inventory.colQty")}</th>
                  <th className="text-left text-[11px] uppercase font-semibold px-3 py-2.5 w-48">{t("inventory.colBatch")}</th>
                  {receiving && <th className="text-right text-[11px] uppercase font-semibold px-3 py-2.5 w-36">{t("inventory.colRate")}</th>}
                  <th className="w-10"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const itemBatches = batches.filter((b) => b.item_code === r.item_code);
                  return (
                    <tr key={i} className="border-t border-divider">
                      <td className="px-3 py-2 muted text-center">{i + 1}</td>
                      <td className="px-2 py-2">
                        <select className={CELL} value={r.item_code} onChange={(e) => pickItem(i, e.target.value)}>
                          <option value="">{t("inventory.selectItem")}</option>
                          {products.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>)}
                        </select>
                      </td>
                      <td className="px-2 py-2">
                        <input className={`${CELL} text-right`} type="number" min="0" step="any" value={r.qty} onChange={(e) => setRow(i, { qty: e.target.value })} />
                      </td>
                      <td className="px-2 py-2">
                        {itemBatches.length > 0 ? (
                          <select className={CELL} value={r.batch_no} onChange={(e) => setRow(i, { batch_no: e.target.value })}>
                            <option value="">{t("inventory.noBatch")}</option>
                            {itemBatches.map((b) => <option key={b.id} value={b.batch_id}>{b.batch_id}</option>)}
                          </select>
                        ) : (
                          <input className={CELL} value={r.batch_no} onChange={(e) => setRow(i, { batch_no: e.target.value })} placeholder={t("inventory.optional")} />
                        )}
                      </td>
                      {receiving && (
                        <td className="px-2 py-2">
                          <input className={`${CELL} text-right`} inputMode="numeric" value={r.rate} onChange={(e) => setRow(i, { rate: groupNum(e.target.value) })} />
                        </td>
                      )}
                      <td className="px-2 py-2 text-center">
                        <button type="button" onClick={() => removeRow(i)} className="icobtn grid place-items-center w-7 h-7 muted hover:text-err" title={t("inventory.remove")}>
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
            <Icon name="plus" size={13} sw={2} /> {t("inventory.addRow")}
          </button>

          <div className="flex justify-end mt-5 pt-4 border-t border-divider">
            <div className="text-right">
              <div className="text-[11px] uppercase muted">{t("inventory.totalQuantity")}</div>
              <div className="font-heading font-semibold text-lg num">{totalQty}</div>
            </div>
          </div>
        </div>
      )}
    </DocFormShell>
  );
}
