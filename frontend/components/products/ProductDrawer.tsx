"use client";

import Drawer, { DetailRow } from "@/components/ui/Drawer";
import { xaf } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Product } from "@/lib/products";

export default function ProductDrawer({
  product,
  onClose,
  onEdit,
}: {
  product: Product;
  onClose: () => void;
  onEdit: () => void;
}) {
  const { t } = useI18n();
  return (
    <Drawer
      eyebrow={product.sku}
      title={product.name}
      onClose={onClose}
      footer={
        <button
          type="button"
          onClick={onEdit}
          className="btn btn-filled"
        >
          {t("products.editProduct")}
        </button>
      }
    >
      <div className="grid grid-cols-2 gap-3 mb-6">
        <div className="blueprint p-4">
          <div className="text-[11px] tracking-[0.1em] uppercase muted mb-1">{t("products.selling")}</div>
          <div className="font-heading font-semibold text-[20px]">
            {product.selling_price != null ? xaf(product.selling_price) : "—"}
          </div>
        </div>
        <div className="blueprint p-4">
          <div className="text-[11px] tracking-[0.1em] uppercase muted mb-1">{t("products.purchase")}</div>
          <div className="font-heading font-semibold text-[20px]">
            {product.purchase_price != null ? xaf(product.purchase_price) : "—"}
          </div>
        </div>
      </div>

      <DetailRow label={t("products.sku")} value={product.sku} />
      <DetailRow label={t("products.category")} value={product.category ?? ""} />
      <DetailRow label={t("products.unit")} value={product.unit} />
      <DetailRow label={t("products.manufacturer")} value={product.manufacturer ?? ""} />
      <DetailRow label={t("products.barcode")} value={product.barcode ?? ""} />
      <DetailRow label={t("common.status")} value={product.disabled ? t("common.disabled") : t("common.active")} />
    </Drawer>
  );
}
