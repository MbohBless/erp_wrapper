"use client";

import Drawer from "@/components/ui/Drawer";
import StatusTag, { invoiceTone } from "@/components/ui/StatusTag";
import { xaf } from "@/lib/api";
import type { SalesInvoice } from "@/lib/sales";

export default function InvoiceDrawer({
  invoice,
  onClose,
}: {
  invoice: SalesInvoice;
  onClose: () => void;
}) {
  return (
    <Drawer eyebrow="Sales invoice" title={invoice.id} onClose={onClose} width="max-w-[460px]">
      <div className="flex justify-between mb-5">
        <div>
          <div className="text-xs muted mb-1">Customer</div>
          <div className="font-medium">{invoice.customer}</div>
        </div>
        <StatusTag label={invoice.status} tone={invoiceTone(invoice.status)} dot={false} />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-6 text-sm">
        <div>
          <div className="text-xs muted mb-1">Posting date</div>
          <div>{invoice.posting_date ?? "—"}</div>
        </div>
        <div>
          <div className="text-xs muted mb-1">Due date</div>
          <div>{invoice.due_date ?? "—"}</div>
        </div>
      </div>

      <LineItems items={invoice.items} />

      <div className="flex justify-between py-1.5 text-sm">
        <span className="muted">Grand total</span>
        <span className="font-semibold">{xaf(invoice.grand_total)}</span>
      </div>
      <div className="flex justify-between py-1.5 text-sm">
        <span className="muted">Outstanding</span>
        <span className="font-semibold">{xaf(invoice.outstanding_amount)}</span>
      </div>
    </Drawer>
  );
}

function LineItems({ items }: { items: SalesInvoice["items"] }) {
  return (
    <>
      <div className="text-[11px] tracking-[0.08em] uppercase muted mb-2">Line items</div>
      <div className="blueprint p-0 overflow-hidden mb-5">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="muted">
              <th className="text-left text-[11px] uppercase font-semibold px-3 py-2 border-b border-divider">
                Item
              </th>
              <th className="text-right text-[11px] uppercase font-semibold px-3 py-2 border-b border-divider">
                Qty
              </th>
              <th className="text-right text-[11px] uppercase font-semibold px-3 py-2 border-b border-divider">
                Amount
              </th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-3 py-4 text-center muted-2">
                  No line items.
                </td>
              </tr>
            ) : (
              items.map((it, i) => (
                <tr key={i} className="border-b border-solid divide-soft">
                  <td className="px-3 py-2">{it.item_code}</td>
                  <td className="px-3 py-2 text-right muted">{it.qty}</td>
                  <td className="px-3 py-2 text-right font-medium">{xaf(it.amount)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
