"use client";

import { useState } from "react";

import type { Customer, CustomerInput, CustomerType } from "@/lib/customers";

const FIELD =
  "eq-field w-full px-3 py-2 text-sm";
const LABEL = "block text-xs muted mb-1.5";

export default function CustomerDialog({
  initial,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Customer | null; // present => edit mode
  busy: boolean;
  error: string | null;
  onSubmit: (input: CustomerInput) => void;
  onCancel: () => void;
}) {
  const editing = !!initial;
  const [form, setForm] = useState<CustomerInput>({
    name: initial?.name ?? "",
    customer_type: initial?.customer_type ?? "Company",
    customer_group: initial?.customer_group ?? "All Customer Groups",
    territory: initial?.territory ?? "All Territories",
    contact_person: initial?.contact_person ?? "",
    phone: initial?.phone ?? "",
    email: initial?.email ?? "",
    address: initial?.address ?? "",
    tax_id: initial?.tax_id ?? "",
    disabled: initial?.disabled ?? false,
  });

  const set = <K extends keyof CustomerInput>(k: K, v: CustomerInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    // Trim empties to null so we don't push blank strings to ERPNext.
    const clean: CustomerInput = {
      ...form,
      contact_person: form.contact_person || null,
      phone: form.phone || null,
      email: form.email || null,
      address: form.address || null,
      tax_id: form.tax_id || null,
    };
    onSubmit(clean);
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
          {editing ? "Edit customer" : "New customer"}
        </h3>

        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          <div className="sm:col-span-2">
            <label className={LABEL}>Account name *</label>
            <input
              className={FIELD}
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              required
              disabled={editing}
              placeholder="e.g. CHU Yaoundé"
            />
          </div>
          <div>
            <label className={LABEL}>Type</label>
            <select
              className={FIELD}
              value={form.customer_type}
              onChange={(e) => set("customer_type", e.target.value as CustomerType)}
            >
              <option value="Company">Company</option>
              <option value="Individual">Individual</option>
            </select>
          </div>
          <div>
            <label className={LABEL}>Territory</label>
            <input
              className={FIELD}
              value={form.territory ?? ""}
              onChange={(e) => set("territory", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Contact person</label>
            <input
              className={FIELD}
              value={form.contact_person ?? ""}
              onChange={(e) => set("contact_person", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Phone</label>
            <input
              className={FIELD}
              value={form.phone ?? ""}
              onChange={(e) => set("phone", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Email</label>
            <input
              className={FIELD}
              type="email"
              value={form.email ?? ""}
              onChange={(e) => set("email", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Tax ID</label>
            <input
              className={FIELD}
              value={form.tax_id ?? ""}
              onChange={(e) => set("tax_id", e.target.value)}
            />
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL}>Address</label>
            <textarea
              className={`${FIELD} min-h-[72px] resize-y`}
              value={form.address ?? ""}
              onChange={(e) => set("address", e.target.value)}
            />
          </div>
          <label className="sm:col-span-2 flex items-center gap-2.5 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={!!form.disabled}
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
            {busy ? "Saving…" : editing ? "Save changes" : "Create customer"}
          </button>
        </div>
      </form>
    </div>
  );
}
