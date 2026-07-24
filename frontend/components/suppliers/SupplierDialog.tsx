"use client";

import { useState } from "react";

import type { Supplier, SupplierInput, SupplierType } from "@/lib/suppliers";

const FIELD = "eq-field w-full px-3 py-2 text-sm";
const LABEL = "block text-xs muted mb-1.5";

export default function SupplierDialog({
  initial,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Supplier | null;
  busy: boolean;
  error: string | null;
  onSubmit: (input: SupplierInput) => void;
  onCancel: () => void;
}) {
  const editing = !!initial;
  const [form, setForm] = useState({
    name: initial?.name ?? "",
    supplier_type: (initial?.supplier_type ?? "Company") as SupplierType,
    supplier_group: initial?.supplier_group ?? "All Supplier Groups",
    contact_person: initial?.contact_person ?? "",
    phone: initial?.phone ?? "",
    email: initial?.email ?? "",
    address: initial?.address ?? "",
    lead_time_days: initial?.lead_time_days?.toString() ?? "",
    tax_id: initial?.tax_id ?? "",
    disabled: initial?.disabled ?? false,
  });
  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-[color-mix(in_srgb,#000_50%,transparent)]"
      onClick={onCancel}
    >
      <form
        className="blueprint w-full max-w-[540px] max-h-[90vh] overflow-y-auto eq-scroll p-6 bg-bg"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          const lt = parseInt(form.lead_time_days, 10);
          onSubmit({
            name: form.name,
            supplier_type: form.supplier_type,
            supplier_group: form.supplier_group || undefined,
            contact_person: form.contact_person || null,
            phone: form.phone || null,
            email: form.email || null,
            address: form.address || null,
            lead_time_days: Number.isNaN(lt) ? null : lt,
            tax_id: form.tax_id || null,
            disabled: form.disabled,
          });
        }}
      >
        <h3 className="font-heading font-semibold text-xl mb-4">
          {editing ? "Edit supplier" : "New supplier"}
        </h3>
        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          <div className="sm:col-span-2">
            <label className={LABEL}>Supplier name *</label>
            <input className={FIELD} value={form.name} onChange={(e) => set("name", e.target.value)} required disabled={editing} placeholder="e.g. Sanofi Cameroun" />
          </div>
          <div>
            <label className={LABEL}>Type</label>
            <select className={FIELD} value={form.supplier_type} onChange={(e) => set("supplier_type", e.target.value)}>
              <option value="Company">Company</option>
              <option value="Individual">Individual</option>
            </select>
          </div>
          <div>
            <label className={LABEL}>Lead time (days)</label>
            <input className={FIELD} type="number" min="0" value={form.lead_time_days} onChange={(e) => set("lead_time_days", e.target.value)} />
          </div>
          <div>
            <label className={LABEL}>Contact person</label>
            <input className={FIELD} value={form.contact_person} onChange={(e) => set("contact_person", e.target.value)} />
          </div>
          <div>
            <label className={LABEL}>Phone</label>
            <input className={FIELD} value={form.phone} onChange={(e) => set("phone", e.target.value)} />
          </div>
          <div>
            <label className={LABEL}>Email</label>
            <input className={FIELD} type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
          </div>
          <div>
            <label className={LABEL}>Tax ID</label>
            <input className={FIELD} value={form.tax_id} onChange={(e) => set("tax_id", e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL}>Address</label>
            <textarea className={`${FIELD} min-h-[64px] resize-y`} value={form.address} onChange={(e) => set("address", e.target.value)} />
          </div>
          <label className="sm:col-span-2 flex items-center gap-2.5 text-sm cursor-pointer">
            <input type="checkbox" checked={form.disabled} onChange={(e) => set("disabled", e.target.checked)} />
            Disabled (hidden from new transactions)
          </label>
        </div>
        <div className="flex justify-end gap-2.5 mt-6">
          <button type="button" onClick={onCancel} className="h-10 px-4 rounded-lg border border-divider text-sm font-heading font-semibold hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]">
            Cancel
          </button>
          <button type="submit" disabled={busy} className="h-10 px-4 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600 disabled:opacity-50">
            {busy ? "Saving…" : editing ? "Save changes" : "Create supplier"}
          </button>
        </div>
      </form>
    </div>
  );
}
