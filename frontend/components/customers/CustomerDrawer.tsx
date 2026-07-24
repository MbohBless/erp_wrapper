"use client";

import Drawer, { DetailRow } from "@/components/ui/Drawer";
import { xaf } from "@/lib/api";
import type { Customer } from "@/lib/customers";

export default function CustomerDrawer({
  customer,
  onClose,
  onEdit,
}: {
  customer: Customer;
  onClose: () => void;
  onEdit: () => void;
}) {
  return (
    <Drawer
      eyebrow={customer.customer_type}
      title={customer.name}
      onClose={onClose}
      footer={
        <button
          type="button"
          onClick={onEdit}
          className="h-10 px-4 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
        >
          Edit customer
        </button>
      }
    >
      <div className="mb-6">
        <div className="text-[11px] tracking-[0.1em] uppercase muted mb-1">
          Outstanding balance
        </div>
        <div className="font-heading font-semibold text-[26px]">
          {customer.outstanding_balance != null ? xaf(customer.outstanding_balance) : "—"}
        </div>
      </div>

      <DetailRow label="Group" value={customer.customer_group} />
      <DetailRow label="Territory" value={customer.territory} />
      <DetailRow label="Contact person" value={customer.contact_person ?? ""} />
      <DetailRow label="Phone" value={customer.phone ?? ""} />
      <DetailRow label="Email" value={customer.email ?? ""} />
      <DetailRow label="Tax ID" value={customer.tax_id ?? ""} />
      <DetailRow label="Address" value={customer.address ?? ""} />
      <DetailRow label="Status" value={customer.disabled ? "Disabled" : "Active"} />

      <div className="mt-6 blueprint p-4">
        <div className="text-sm font-semibold mb-1">Purchase history</div>
        <div className="text-[13px] muted">
          Linked sales invoices will appear here once the Sales module is connected.
        </div>
      </div>
    </Drawer>
  );
}
