"use client";

import { useState } from "react";

import type { BatchInput } from "@/lib/inventory";

const FIELD = "eq-field w-full px-3 py-2 text-sm";
const LABEL = "block text-xs muted mb-1.5";

export default function BatchDialog({
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  busy: boolean;
  error: string | null;
  onSubmit: (input: BatchInput) => void;
  onCancel: () => void;
}) {
  const [batchId, setBatchId] = useState("");
  const [itemCode, setItemCode] = useState("");
  const [expiry, setExpiry] = useState("");
  const [mfg, setMfg] = useState("");

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-[color-mix(in_srgb,#000_50%,transparent)]"
      onClick={onCancel}
    >
      <form
        className="blueprint w-full max-w-[440px] p-6 bg-bg"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({
            batch_id: batchId,
            item_code: itemCode,
            expiry_date: expiry || null,
            manufacturing_date: mfg || null,
          });
        }}
      >
        <h3 className="font-heading font-semibold text-xl mb-4">New batch</h3>
        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3.5">
          <div>
            <label className={LABEL}>Batch number *</label>
            <input
              className={FIELD}
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              required
              placeholder="MET-7781"
            />
          </div>
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
            <label className={LABEL}>Expiry date</label>
            <input
              className={FIELD}
              type="date"
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Manufacturing date</label>
            <input
              className={FIELD}
              type="date"
              value={mfg}
              onChange={(e) => setMfg(e.target.value)}
            />
          </div>
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
            disabled={busy}
            className="h-10 px-4 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600 disabled:opacity-50"
          >
            {busy ? "Saving…" : "Create batch"}
          </button>
        </div>
      </form>
    </div>
  );
}
