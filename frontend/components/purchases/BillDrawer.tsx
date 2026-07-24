"use client";

import Drawer from "@/components/ui/Drawer";
import StatusTag, { invoiceTone } from "@/components/ui/StatusTag";
import { xaf } from "@/lib/api";
import type { PurchaseInvoice } from "@/lib/purchases";

export default function BillDrawer({
  bill,
  onClose,
}: {
  bill: PurchaseInvoice;
  onClose: () => void;
}) {
  return (
    <Drawer eyebrow="Purchase invoice" title={bill.id} onClose={onClose} width="max-w-[460px]">
      <div className="flex justify-between mb-5">
        <div>
          <div className="text-xs muted mb-1">Supplier</div>
          <div className="font-medium">{bill.supplier}</div>
        </div>
        <StatusTag label={bill.status} tone={invoiceTone(bill.status)} dot={false} />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-6 text-sm">
        <div>
          <div className="text-xs muted mb-1">Posting date</div>
          <div>{bill.posting_date ?? "—"}</div>
        </div>
        <div>
          <div className="text-xs muted mb-1">Supplier bill no.</div>
          <div>{bill.bill_no ?? "—"}</div>
        </div>
      </div>

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
            {bill.items.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-3 py-4 text-center muted-2">
                  No line items.
                </td>
              </tr>
            ) : (
              bill.items.map((it, i) => (
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

      <div className="flex justify-between py-1.5 text-sm">
        <span className="muted">Grand total</span>
        <span className="font-semibold">{xaf(bill.grand_total)}</span>
      </div>
      <div className="flex justify-between py-1.5 text-sm">
        <span className="muted">Outstanding</span>
        <span className="font-semibold">{xaf(bill.outstanding_amount)}</span>
      </div>
    </Drawer>
  );
}
