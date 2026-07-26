"use client";

import Drawer, { DetailRow } from "@/components/ui/Drawer";
import { useI18n } from "@/lib/i18n";
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
  const { t } = useI18n();
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
              className="btn btn-outlined"
            >
              {installing ? t("equipment.installing") : t("equipment.markInstalled")}
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
      <DetailRow label={t("equipment.field.product")} value={equipment.item_name || equipment.item_code} />
      <DetailRow label={t("equipment.field.skuShort")} value={equipment.item_code} />
      <DetailRow label={t("equipment.field.customer")} value={equipment.customer ?? ""} />
      <DetailRow label={t("equipment.field.installDate")} value={equipment.installation_date ?? ""} />
      <DetailRow label={t("equipment.field.warranty")} value={equipment.warranty_expiry_date ?? ""} />
      <DetailRow label={t("common.status")} value={equipment.status} />
    </Drawer>
  );
}
