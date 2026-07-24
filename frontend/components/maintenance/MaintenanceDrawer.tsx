"use client";

import Drawer, { DetailRow } from "@/components/ui/Drawer";
import type { Ticket } from "@/lib/maintenance";

export default function MaintenanceDrawer({
  ticket,
  onClose,
  onEdit,
  onComplete,
  completing,
}: {
  ticket: Ticket;
  onClose: () => void;
  onEdit: () => void;
  onComplete: () => void;
  completing: boolean;
}) {
  const canComplete = ticket.status !== "Completed" && ticket.status !== "Cancelled";
  return (
    <Drawer
      eyebrow={ticket.status}
      title={ticket.id}
      onClose={onClose}
      footer={
        <>
          {canComplete && (
            <button
              type="button"
              onClick={onComplete}
              disabled={completing}
              className="h-10 px-4 rounded-lg border border-divider text-sm font-heading font-semibold hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)] disabled:opacity-50"
            >
              {completing ? "Completing…" : "Complete & sign"}
            </button>
          )}
          <button
            type="button"
            onClick={onEdit}
            className="h-10 px-4 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
          >
            Edit
          </button>
        </>
      }
    >
      <DetailRow label="Customer" value={ticket.customer} />
      <DetailRow label="Equipment" value={ticket.equipment ?? ""} />
      <DetailRow label="Engineer" value={ticket.engineer ?? ""} />
      <DetailRow label="Visit date" value={ticket.visit_date ?? ""} />
      <DetailRow label="Status" value={ticket.status} />
      <DetailRow
        label="Customer signature"
        value={ticket.customer_signed ? "Signed" : "Not signed"}
      />

      {ticket.description && (
        <div className="mt-5">
          <div className="text-[11px] tracking-[0.08em] uppercase muted mb-1.5">
            Description
          </div>
          <div className="text-sm">{ticket.description}</div>
        </div>
      )}
      {ticket.parts_used && (
        <div className="mt-5">
          <div className="text-[11px] tracking-[0.08em] uppercase muted mb-1.5">
            Parts used
          </div>
          <div className="text-sm">{ticket.parts_used}</div>
        </div>
      )}
    </Drawer>
  );
}
