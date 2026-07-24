"use client";

import { useState } from "react";

import type { Warehouse, WarehouseInput } from "@/lib/inventory";

const FIELD = "eq-field w-full px-3 py-2 text-sm";
const LABEL = "block text-xs muted mb-1.5";

export default function WarehouseDialog({
  initial,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Warehouse | null;
  busy: boolean;
  error: string | null;
  onSubmit: (input: WarehouseInput) => void;
  onCancel: () => void;
}) {
  const editing = !!initial;
  const [name, setName] = useState(initial?.name ?? "");
  const [parent, setParent] = useState(initial?.parent_warehouse ?? "");
  const [isGroup, setIsGroup] = useState(initial?.is_group ?? false);
  const [disabled, setDisabled] = useState(initial?.disabled ?? false);

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
            name,
            parent_warehouse: parent || null,
            is_group: isGroup,
            disabled,
          });
        }}
      >
        <h3 className="font-heading font-semibold text-xl mb-4">
          {editing ? "Edit warehouse" : "New warehouse"}
        </h3>
        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}
        <div className="mb-3.5">
          <label className={LABEL}>Warehouse name *</label>
          <input
            className={FIELD}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            disabled={editing}
            placeholder="e.g. WH Douala"
          />
        </div>
        <div className="mb-3.5">
          <label className={LABEL}>Parent warehouse</label>
          <input
            className={FIELD}
            value={parent}
            onChange={(e) => setParent(e.target.value)}
            placeholder="Optional"
          />
        </div>
        <div className="flex flex-col gap-2.5 mb-2">
          <label className="flex items-center gap-2.5 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={isGroup}
              onChange={(e) => setIsGroup(e.target.checked)}
            />
            Group warehouse (holds sub-warehouses)
          </label>
          <label className="flex items-center gap-2.5 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={disabled}
              onChange={(e) => setDisabled(e.target.checked)}
            />
            Disabled
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
            {busy ? "Saving…" : editing ? "Save changes" : "Create warehouse"}
          </button>
        </div>
      </form>
    </div>
  );
}
