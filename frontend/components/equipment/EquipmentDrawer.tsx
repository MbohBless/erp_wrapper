"use client";

import Drawer, { DetailRow } from "@/components/ui/Drawer";
import type { Equipment } from "@/lib/equipment";

export default function EquipmentDrawer({
  equipment,
  onClose,
  onEdit,
  onInstall,
  installing,
}: {
  equipment: Equipment;
  onClose: () => void;
  onEdit: () => void;
  onInstall: () => void;
  installing: boolean;
}) {
  const canInstall = equipment.status !== "Installed";
  return (
    <Drawer
      eyebrow={equipment.status}
      title={equipment.serial_no}
      onClose={onClose}
      footer={
        <>
          {canInstall && (
            <button
              type="button"
              onClick={onInstall}
              disabled={installing}
              className="h-10 px-4 rounded-lg border border-divider text-sm font-heading font-semibold hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)] disabled:opacity-50"
            >
              {installing ? "Installing…" : "Mark installed"}
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
      <DetailRow label="Product" value={equipment.item_name || equipment.item_code} />
      <DetailRow label="SKU" value={equipment.item_code} />
      <DetailRow label="Customer / site" value={equipment.customer ?? ""} />
      <DetailRow label="Installation date" value={equipment.installation_date ?? ""} />
      <DetailRow label="Warranty expiry" value={equipment.warranty_expiry_date ?? ""} />
      <DetailRow label="Status" value={equipment.status} />
    </Drawer>
  );
}
