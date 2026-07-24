"use client";

import { useState } from "react";

import type { Product, ProductInput } from "@/lib/products";

const FIELD = "eq-field w-full px-3 py-2 text-sm";
const LABEL = "block text-xs muted mb-1.5";

type FormState = {
  name: string;
  sku: string;
  category: string;
  unit: string;
  manufacturer: string;
  barcode: string;
  purchase_price: string;
  selling_price: string;
  image: string;
  disabled: boolean;
};

const num = (s: string): number | null => {
  const n = parseFloat(s);
  return s.trim() === "" || Number.isNaN(n) ? null : n;
};

export default function ProductDialog({
  initial,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Product | null; // present => edit mode
  busy: boolean;
  error: string | null;
  onSubmit: (input: ProductInput) => void;
  onCancel: () => void;
}) {
  const editing = !!initial;
  const [form, setForm] = useState<FormState>({
    name: initial?.name ?? "",
    sku: initial?.sku ?? "",
    category: initial?.category ?? "All Item Groups",
    unit: initial?.unit ?? "Nos",
    manufacturer: initial?.manufacturer ?? "",
    barcode: initial?.barcode ?? "",
    purchase_price: initial?.purchase_price?.toString() ?? "",
    selling_price: initial?.selling_price?.toString() ?? "",
    image: initial?.image ?? "",
    disabled: initial?.disabled ?? false,
  });

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      name: form.name,
      sku: form.sku,
      category: form.category || undefined,
      unit: form.unit || undefined,
      manufacturer: form.manufacturer || null,
      barcode: form.barcode || null,
      purchase_price: num(form.purchase_price),
      selling_price: num(form.selling_price),
      image: form.image || null,
      disabled: form.disabled,
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-[color-mix(in_srgb,#000_50%,transparent)]"
      onClick={onCancel}
    >
      <form
        className="blueprint w-full max-w-[540px] max-h-[90vh] overflow-y-auto eq-scroll p-6 bg-bg"
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <h3 className="font-heading font-semibold text-xl mb-4">
          {editing ? "Edit product" : "New product"}
        </h3>

        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          <div className="sm:col-span-2">
            <label className={LABEL}>Product name *</label>
            <input
              className={FIELD}
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              required
              placeholder="e.g. Digital Thermometer"
            />
          </div>
          <div>
            <label className={LABEL}>SKU *</label>
            <input
              className={FIELD}
              value={form.sku}
              onChange={(e) => set("sku", e.target.value)}
              required
              disabled={editing}
              placeholder="THERMO-001"
            />
          </div>
          <div>
            <label className={LABEL}>Category</label>
            <input
              className={FIELD}
              value={form.category}
              onChange={(e) => set("category", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Unit</label>
            <input
              className={FIELD}
              value={form.unit}
              onChange={(e) => set("unit", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Manufacturer</label>
            <input
              className={FIELD}
              value={form.manufacturer}
              onChange={(e) => set("manufacturer", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Purchase price (XAF)</label>
            <input
              className={FIELD}
              type="number"
              min="0"
              step="0.01"
              value={form.purchase_price}
              onChange={(e) => set("purchase_price", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Selling price (XAF)</label>
            <input
              className={FIELD}
              type="number"
              min="0"
              step="0.01"
              value={form.selling_price}
              onChange={(e) => set("selling_price", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Barcode</label>
            <input
              className={FIELD}
              value={form.barcode}
              onChange={(e) => set("barcode", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Image URL</label>
            <input
              className={FIELD}
              value={form.image}
              onChange={(e) => set("image", e.target.value)}
            />
          </div>
          <label className="sm:col-span-2 flex items-center gap-2.5 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={form.disabled}
              onChange={(e) => set("disabled", e.target.checked)}
            />
            Disabled (hidden from new transactions)
          </label>
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
            {busy ? "Saving…" : editing ? "Save changes" : "Create product"}
          </button>
        </div>
      </form>
    </div>
  );
}
