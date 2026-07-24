"use client";

import { useState } from "react";

import type { MovementInput, Warehouse } from "@/lib/inventory";

const FIELD = "eq-field w-full px-3 py-2 text-sm";
const LABEL = "block text-xs muted mb-1.5";

export default function GoodsMovementDialog({
  mode,
  warehouses,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  mode: "receive" | "issue";
  warehouses: Warehouse[];
  busy: boolean;
  error: string | null;
  onSubmit: (input: MovementInput) => void;
  onCancel: () => void;
}) {
  const receiving = mode === "receive";
  const [warehouse, setWarehouse] = useState(warehouses[0]?.id ?? "");
  const [itemCode, setItemCode] = useState("");
  const [qty, setQty] = useState("");
  const [batch, setBatch] = useState("");
  const [rate, setRate] = useState("");

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-[color-mix(in_srgb,#000_50%,transparent)]"
      onClick={onCancel}
    >
      <form
        className="blueprint w-full max-w-[460px] p-6 bg-bg"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({
            warehouse,
            items: [
              {
                item_code: itemCode,
                qty: parseFloat(qty) || 0,
                batch_no: batch || null,
                rate: receiving && rate ? parseFloat(rate) : null,
              },
            ],
          });
        }}
      >
        <h3 className="font-heading font-semibold text-xl mb-1">
          {receiving ? "Receive goods" : "Issue goods"}
        </h3>
        <p className="muted text-[13px] mb-4">
          {receiving
            ? "Add stock into a warehouse (Material Receipt)."
            : "Remove stock from a warehouse (Material Issue)."}
        </p>
        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}
        <div className="mb-3.5">
          <label className={LABEL}>{receiving ? "Target" : "Source"} warehouse *</label>
          <select
            className={FIELD}
            value={warehouse}
            onChange={(e) => setWarehouse(e.target.value)}
            required
          >
            {warehouses.length === 0 && <option value="">No warehouses</option>}
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3.5">
          <div>
            <label className={LABEL}>Product (SKU) *</label>
            <input
              className={FIELD}
              value={itemCode}
              onChange={(e) => setItemCode(e.target.value)}
              required
              placeholder="THERMO-001"
            />
          </div>
          <div>
            <label className={LABEL}>Quantity *</label>
            <input
              className={FIELD}
              type="number"
              min="0.01"
              step="any"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              required
            />
          </div>
          <div>
            <label className={LABEL}>Batch (optional)</label>
            <input
              className={FIELD}
              value={batch}
              onChange={(e) => setBatch(e.target.value)}
            />
          </div>
          {receiving && (
            <div>
              <label className={LABEL}>Rate / unit (XAF)</label>
              <input
                className={FIELD}
                type="number"
                min="0"
                step="any"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
              />
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2.5 mt-6">
          <button
            type="button"
            onClick={onCancel}
            className="h-10 px-4 rounded-lg border border-divider text-sm font-heading font-semibold hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy || !warehouse}
            className="h-10 px-4 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600 disabled:opacity-50"
          >
            {busy ? "Posting…" : receiving ? "Receive" : "Issue"}
          </button>
        </div>
      </form>
    </div>
  );
}
