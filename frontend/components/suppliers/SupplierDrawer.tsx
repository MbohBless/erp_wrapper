"use client";

import Drawer, { DetailRow } from "@/components/ui/Drawer";
import type { Supplier } from "@/lib/suppliers";

export default function SupplierDrawer({
  supplier,
  onClose,
  onEdit,
}: {
  supplier: Supplier;
  onClose: () => void;
  onEdit: () => void;
}) {
  return (
    <Drawer
      eyebrow={supplier.supplier_type}
      title={supplier.name}
      onClose={onClose}
      footer={
        <button
          type="button"
          onClick={onEdit}
          className="h-10 px-4 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
        >
          Edit supplier
        </button>
      }
    >
      <DetailRow label="Group" value={supplier.supplier_group} />
      <DetailRow label="Contact person" value={supplier.contact_person ?? ""} />
      <DetailRow label="Phone" value={supplier.phone ?? ""} />
      <DetailRow label="Email" value={supplier.email ?? ""} />
      <DetailRow
        label="Lead time"
        value={supplier.lead_time_days != null ? `${supplier.lead_time_days} days` : ""}
      />
      <DetailRow label="Tax ID" value={supplier.tax_id ?? ""} />
      <DetailRow label="Address" value={supplier.address ?? ""} />
      <DetailRow label="Status" value={supplier.disabled ? "Disabled" : "Active"} />
    </Drawer>
  );
}
