"use client";

import { useState } from "react";

import type { MaintenanceStatus, Ticket, TicketInput } from "@/lib/maintenance";

const FIELD = "eq-field w-full px-3 py-2 text-sm";
const LABEL = "block text-xs muted mb-1.5";
const STATUSES: MaintenanceStatus[] = [
  "Open",
  "Scheduled",
  "In Progress",
  "Completed",
  "Cancelled",
];

export default function MaintenanceDialog({
  initial,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Ticket | null;
  busy: boolean;
  error: string | null;
  onSubmit: (input: TicketInput) => void;
  onCancel: () => void;
}) {
  const editing = !!initial;
  const [form, setForm] = useState<TicketInput>({
    customer: initial?.customer ?? "",
    equipment: initial?.equipment ?? "",
    engineer: initial?.engineer ?? "",
    visit_date: initial?.visit_date ?? "",
    status: initial?.status ?? "Open",
    description: initial?.description ?? "",
    parts_used: initial?.parts_used ?? "",
  });

  const set = <K extends keyof TicketInput>(k: K, v: TicketInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-[color-mix(in_srgb,#000_50%,transparent)]"
      onClick={onCancel}
    >
      <form
        className="blueprint w-full max-w-[560px] max-h-[90vh] overflow-y-auto eq-scroll p-6 bg-bg"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({
            ...form,
            equipment: form.equipment || null,
            engineer: form.engineer || null,
            visit_date: form.visit_date || null,
            description: form.description || null,
            parts_used: form.parts_used || null,
          });
        }}
      >
        <h3 className="font-heading font-semibold text-xl mb-4">
          {editing ? "Edit ticket" : "New service ticket"}
        </h3>
        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          <div>
            <label className={LABEL}>Customer *</label>
            <input
              className={FIELD}
              value={form.customer}
              onChange={(e) => set("customer", e.target.value)}
              required
            />
          </div>
          <div>
            <label className={LABEL}>Equipment (serial)</label>
            <input
              className={FIELD}
              value={form.equipment ?? ""}
              onChange={(e) => set("equipment", e.target.value)}
              placeholder="VENT-0001"
            />
          </div>
          <div>
            <label className={LABEL}>Assigned engineer</label>
            <input
              className={FIELD}
              value={form.engineer ?? ""}
              onChange={(e) => set("engineer", e.target.value)}
            />
          </div>
          <div>
            <label className={LABEL}>Visit date</label>
            <input
              className={FIELD}
              type="date"
              value={form.visit_date ?? ""}
              onChange={(e) => set("visit_date", e.target.value)}
            />
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL}>Status</label>
            <select
              className={FIELD}
              value={form.status}
              onChange={(e) => set("status", e.target.value as MaintenanceStatus)}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL}>Description</label>
            <textarea
              className={`${FIELD} min-h-[64px] resize-y`}
              value={form.description ?? ""}
              onChange={(e) => set("description", e.target.value)}
            />
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL}>Parts used</label>
            <textarea
              className={`${FIELD} min-h-[56px] resize-y`}
              value={form.parts_used ?? ""}
              onChange={(e) => set("parts_used", e.target.value)}
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
            {busy ? "Saving…" : editing ? "Save changes" : "Create ticket"}
          </button>
        </div>
      </form>
    </div>
  );
}
