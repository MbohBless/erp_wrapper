"use client";

import Drawer, { DetailRow } from "@/components/ui/Drawer";
import { useI18n } from "@/lib/i18n";
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
  const { t } = useI18n();
  return (
    <Drawer
      eyebrow={supplier.supplier_type}
      title={supplier.name}
      onClose={onClose}
      footer={
        <button
          type="button"
          onClick={onEdit}
          className="btn btn-filled"
        >
          {t("suppliers.drawer.edit")}
        </button>
      }
    >
      <DetailRow label={t("suppliers.detail.group")} value={supplier.supplier_group} />
      <DetailRow label={t("suppliers.detail.contactPerson")} value={supplier.contact_person ?? ""} />
      <DetailRow label={t("suppliers.detail.phone")} value={supplier.phone ?? ""} />
      <DetailRow label={t("suppliers.detail.email")} value={supplier.email ?? ""} />
      <DetailRow
        label={t("suppliers.detail.leadTime")}
        value={supplier.lead_time_days != null ? `${supplier.lead_time_days} ${t("suppliers.days")}` : ""}
      />
      <DetailRow label={t("suppliers.detail.taxId")} value={supplier.tax_id ?? ""} />
      <DetailRow label={t("suppliers.detail.address")} value={supplier.address ?? ""} />
      <DetailRow label={t("common.status")} value={supplier.disabled ? t("common.disabled") : t("common.active")} />
    </Drawer>
  );
}
