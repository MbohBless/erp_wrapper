"use client";

import Drawer, { DetailRow } from "@/components/ui/Drawer";
import { xaf } from "@/lib/api";
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
  return (
    <Drawer
      eyebrow={product.sku}
      title={product.name}
      onClose={onClose}
      footer={
        <button
          type="button"
          onClick={onEdit}
          className="h-10 px-4 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
        >
          Edit product
        </button>
      }
    >
      <div className="grid grid-cols-2 gap-3 mb-6">
        <div className="blueprint p-4">
          <div className="text-[11px] tracking-[0.1em] uppercase muted mb-1">Selling</div>
          <div className="font-heading font-semibold text-[20px]">
            {product.selling_price != null ? xaf(product.selling_price) : "—"}
          </div>
        </div>
        <div className="blueprint p-4">
          <div className="text-[11px] tracking-[0.1em] uppercase muted mb-1">Purchase</div>
          <div className="font-heading font-semibold text-[20px]">
            {product.purchase_price != null ? xaf(product.purchase_price) : "—"}
          </div>
        </div>
      </div>

      <DetailRow label="SKU" value={product.sku} />
      <DetailRow label="Category" value={product.category} />
      <DetailRow label="Unit" value={product.unit} />
      <DetailRow label="Manufacturer" value={product.manufacturer ?? ""} />
      <DetailRow label="Barcode" value={product.barcode ?? ""} />
      <DetailRow label="Status" value={product.disabled ? "Disabled" : "Active"} />
    </Drawer>
  );
}
