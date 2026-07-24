"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Icon } from "@/components/icons";
import { xaf } from "@/lib/api";
import type { PurchaseInput } from "@/lib/purchases";
import { listSuppliers } from "@/lib/suppliers";

const FIELD = "eq-field w-full px-3 py-2 text-sm";
const LABEL = "block text-xs muted mb-1.5";

type Line = { item_code: string; qty: string; rate: string };
const emptyLine = (): Line => ({ item_code: "", qty: "1", rate: "" });

export default function BillDialog({
  token,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  token: string;
  busy: boolean;
  error: string | null;
  onSubmit: (input: PurchaseInput) => void;
  onCancel: () => void;
}) {
  const [supplier, setSupplier] = useState("");
  const [billNo, setBillNo] = useState("");
  const [lines, setLines] = useState<Line[]>([emptyLine()]);

  const suppliersQ = useQuery({
    queryKey: ["suppliers-lite"],
    queryFn: () => listSuppliers(token),
  });

  const setLine = (i: number, patch: Partial<Line>) =>
    setLines((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  const addLine = () => setLines((ls) => [...ls, emptyLine()]);
  const removeLine = (i: number) =>
    setLines((ls) => (ls.length > 1 ? ls.filter((_, idx) => idx !== i) : ls));

  const total = lines.reduce(
    (s, l) => s + (parseFloat(l.qty) || 0) * (parseFloat(l.rate) || 0),
    0
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      supplier,
      bill_no: billNo || null,
      items: lines
        .filter((l) => l.item_code.trim())
        .map((l) => ({
          item_code: l.item_code.trim(),
          qty: parseFloat(l.qty) || 0,
          rate: parseFloat(l.rate) || 0,
        })),
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-[color-mix(in_srgb,#000_50%,transparent)]"
      onClick={onCancel}
    >
      <form
        className="blueprint w-full max-w-[620px] max-h-[90vh] overflow-y-auto eq-scroll p-6 bg-bg"
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <h3 className="font-heading font-semibold text-xl mb-4">New purchase</h3>
        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 mb-4">
          <div>
            <label className={LABEL}>Supplier *</label>
            <select
              className={FIELD}
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
              required
            >
              <option value="">Select a supplier…</option>
              {(suppliersQ.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={LABEL}>Supplier bill no.</label>
            <input
              className={FIELD}
              value={billNo}
              onChange={(e) => setBillNo(e.target.value)}
              placeholder="Their invoice number"
            />
          </div>
        </div>

        <label className={LABEL}>Line items</label>
        <div className="flex flex-col gap-2 mb-2">
          {lines.map((l, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                className={`${FIELD} flex-1`}
                placeholder="Product SKU"
                value={l.item_code}
                onChange={(e) => setLine(i, { item_code: e.target.value })}
              />
              <input
                className={`${FIELD} w-20`}
                type="number"
                min="0.01"
                step="any"
                placeholder="Qty"
                value={l.qty}
                onChange={(e) => setLine(i, { qty: e.target.value })}
              />
              <input
                className={`${FIELD} w-28`}
                type="number"
                min="0"
                step="any"
                placeholder="Rate"
                value={l.rate}
                onChange={(e) => setLine(i, { rate: e.target.value })}
              />
              <button
                type="button"
                onClick={() => removeLine(i)}
                className="icobtn grid place-items-center w-8 h-8 shrink-0 muted hover:text-err"
                title="Remove line"
              >
                <Icon name="trash" size={15} />
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addLine}
          className="text-[13px] text-accent inline-flex items-center gap-1 mb-4"
        >
          <Icon name="plus" size={13} sw={2} /> Add line
        </button>

        <div className="flex justify-between items-center pt-3 border-t border-divider mb-5">
          <span className="text-sm muted">Estimated total</span>
          <span className="font-heading font-semibold text-lg">{xaf(total)}</span>
        </div>

        <div className="flex justify-end gap-2.5">
          <button
            type="button"
            onClick={onCancel}
            className="h-10 px-4 rounded-lg border border-divider text-sm font-heading font-semibold hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy || !supplier}
            className="h-10 px-4 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600 disabled:opacity-50"
          >
            {busy ? "Posting…" : "Create purchase"}
          </button>
        </div>
      </form>
    </div>
  );
}
