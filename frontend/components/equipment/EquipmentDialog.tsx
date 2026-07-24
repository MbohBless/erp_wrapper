"use client";

import { useState } from "react";

import type {
  Equipment,
  EquipmentInput,
  EquipmentStatus,
} from "@/lib/equipment";

const FIELD = "eq-field w-full px-3 py-2 text-sm";
const LABEL = "block text-xs muted mb-1.5";
const STATUSES: EquipmentStatus[] = [
  "In Store",
  "Installed",
  "Under Repair",
  "Decommissioned",
];

export default function EquipmentDialog({
  initial,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Equipment | null;
  busy: boolean;
  error: string | null;
  onSubmit: (input: EquipmentInput) => void;
  onCancel: () => void;
}) {
  const editing = !!initial;
  const [form, setForm] = useState<EquipmentInput>({
    serial_no: initial?.serial_no ?? "",
    item_code: initial?.item_code ?? "",
    customer: initial?.customer ?? "",
    installation_date: initial?.installation_date ?? "",
    warranty_expiry_date: initial?.warranty_expiry_date ?? "",
    status: initial?.status ?? "In Store",
  });

  const set = <K extends keyof EquipmentInput>(k: K, v: EquipmentInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-[color-mix(in_srgb,#000_50%,transparent)]"
      onClick={onCancel}
    >
      <form
        className="blueprint w-full max-w-[520px] p-6 bg-bg"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({
            ...form,
            customer: form.customer || null,
            installation_date: form.installation_date || null,
            warranty_expiry_date: form.warranty_expiry_date || null,
          });
        }}
      >
        <h3 className="font-heading font-semibold text-xl mb-4">
          {editing ? "Edit equipment" : "Register equipment"}
        </h3>
        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          <div>
            <label className={LABEL}>Serial number *</label>
            <input
              className={FIELD}
              value={form.serial_no}
              onChange={(e) => set("serial_no", e.target.value)}
              required
              disabled={editing}
              placeholder="VENT-0001"
            />
          </div>
          <div>
            <label className={LABEL}>Product (SKU) *</label>
            <input
              className={FIELD}
              value={form.item_code}
              onChange={(e) => set("item_code", e.target.value)}
              required
              placeholder="VENTILATOR-X"
            />
          </div>
          <div>
            <label className={LABEL}>Customer / site</label>
            <input
              className={FIELD}
              value={form.customer ?? ""}
              onChange={(e) => set("customer", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Status</label>
            <select
              className={FIELD}
              value={form.status}
              onChange={(e) => set("status", e.target.value as EquipmentStatus)}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={LABEL}>Installation date</label>
            <input
              className={FIELD}
              type="date"
              value={form.installation_date ?? ""}
              onChange={(e) => set("installation_date", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Warranty expiry</label>
            <input
              className={FIELD}
              type="date"
              value={form.warranty_expiry_date ?? ""}
              onChange={(e) => set("warranty_expiry_date", e.target.value)}
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
            {busy ? "Saving…" : editing ? "Save changes" : "Register"}
          </button>
        </div>
      </form>
    </div>
  );
}
