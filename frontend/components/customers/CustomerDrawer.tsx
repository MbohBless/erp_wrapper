"use client";

import Drawer, { DetailRow } from "@/components/ui/Drawer";
import { xaf } from "@/lib/api";
import type { Customer } from "@/lib/customers";
import { useI18n } from "@/lib/i18n";

export default function CustomerDrawer({
  customer,
  onClose,
  onEdit,
}: {
  customer: Customer;
  onClose: () => void;
  onEdit: () => void;
}) {
  const { t } = useI18n();
  return (
    <Drawer
      eyebrow={customer.customer_type}
      title={customer.name}
      onClose={onClose}
      footer={
        <button
          type="button"
          onClick={onEdit}
          className="btn btn-filled"
        >
          {t("customers.drawer.edit")}
        </button>
      }
    >
      <div className="mb-6">
        <div className="text-[11px] tracking-[0.1em] uppercase muted mb-1">
          {t("customers.outstandingBalance")}
        </div>
        <div className="font-heading font-semibold text-[26px]">
          {customer.outstanding_balance != null ? xaf(customer.outstanding_balance) : "—"}
        </div>
      </div>

      <DetailRow label={t("customers.detail.group")} value={customer.customer_group} />
      <DetailRow label={t("customers.detail.territory")} value={customer.territory} />
      <DetailRow label={t("customers.detail.contactPerson")} value={customer.contact_person ?? ""} />
      <DetailRow label={t("customers.detail.phone")} value={customer.phone ?? ""} />
      <DetailRow label={t("customers.detail.email")} value={customer.email ?? ""} />
      <DetailRow label={t("customers.detail.taxId")} value={customer.tax_id ?? ""} />
      <DetailRow label={t("customers.detail.address")} value={customer.address ?? ""} />
      <DetailRow label={t("common.status")} value={customer.disabled ? t("common.disabled") : t("common.active")} />

      <div className="mt-6 blueprint p-4">
        <div className="text-sm font-semibold mb-1">{t("customers.purchaseHistory")}</div>
        <div className="text-[13px] muted">
          {t("customers.purchaseHistoryHint")}
        </div>
      </div>
    </Drawer>
  );
}
