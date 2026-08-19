import type { TenantStatus } from "@/lib/tenants";

/**
 * Status is never colour-alone: every badge carries its label, so the state is
 * legible to a colourblind operator and in a screenshot pasted into a ticket.
 */
const STYLES: Record<TenantStatus, string> = {
  active: "bg-[color-mix(in_srgb,var(--ok)_18%,transparent)] text-ok",
  suspended: "bg-[color-mix(in_srgb,var(--err)_18%,transparent)] text-err",
  provisioning: "bg-[color-mix(in_srgb,var(--warn)_18%,transparent)] text-warn",
  pending: "bg-[color-mix(in_srgb,var(--color-text)_10%,transparent)] muted",
  archived: "bg-[color-mix(in_srgb,var(--color-text)_10%,transparent)] muted-2",
};

export default function StatusBadge({ status }: { status: TenantStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium capitalize ${
        STYLES[status] ?? STYLES.pending
      }`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {status}
    </span>
  );
}
