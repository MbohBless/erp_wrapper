"use client";

import Drawer, { DetailRow } from "@/components/ui/Drawer";
import { useI18n } from "@/lib/i18n";
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
  const { t } = useI18n();
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
              className="btn btn-outlined"
            >
              {completing ? t("maintenance.completing") : t("maintenance.complete")}
            </button>
          )}
          <button
            type="button"
            onClick={onEdit}
            className="btn btn-filled"
          >
            {t("action.edit")}
          </button>
        </>
      }
    >
      <DetailRow label={t("maintenance.field.customer")} value={ticket.customer} />
      <DetailRow label={t("maintenance.col.equipment")} value={ticket.equipment ?? ""} />
      <DetailRow label={t("maintenance.field.engineerShort")} value={ticket.engineer ?? ""} />
      <DetailRow label={t("maintenance.field.visitDate")} value={ticket.visit_date ?? ""} />
      <DetailRow label={t("common.status")} value={ticket.status} />
      <DetailRow
        label={t("maintenance.field.signature")}
        value={ticket.customer_signed ? t("maintenance.signed") : t("maintenance.notSigned")}
      />

      {ticket.description && (
        <div className="mt-5">
          <div className="text-[11px] tracking-[0.08em] uppercase muted mb-1.5">
            {t("maintenance.field.description")}
          </div>
          <div className="text-sm">{ticket.description}</div>
        </div>
      )}
      {ticket.parts_used && (
        <div className="mt-5">
          <div className="text-[11px] tracking-[0.08em] uppercase muted mb-1.5">
            {t("maintenance.field.parts")}
          </div>
          <div className="text-sm">{ticket.parts_used}</div>
        </div>
      )}
    </Drawer>
  );
}
