"use client";

import Modal from "@/components/ui/Modal";

export default function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  busy = false,
  error,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  busy?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal onClose={onCancel} className="max-w-[420px]">
      <div className="p-6">
        <h3 className="font-heading font-semibold text-xl mb-2">{title}</h3>
        <p className="text-sm muted mb-4">{message}</p>
        {error && (
          <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2 rounded-lg text-[13px] mb-4">
            {error}
          </div>
        )}
        <div className="flex justify-end gap-2.5">
          <button
            type="button"
            onClick={onCancel}
            className="h-9 px-4 rounded-lg border border-divider text-sm font-heading font-semibold hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="h-9 px-4 rounded-lg bg-err text-white text-sm font-heading font-semibold disabled:opacity-50"
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}
