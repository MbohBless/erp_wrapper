"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { getSale } from "@/lib/sales";

import Drawer from "@/components/ui/Drawer";
import StatusTag, { invoiceTone } from "@/components/ui/StatusTag";
import { xaf } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { amendBlockedReason, type SalesInvoice } from "@/lib/sales";

export default function InvoiceDrawer({
  invoice,
  onClose,
  onRecordPayment,
  onEdit,
}: {
  invoice: SalesInvoice;
  onClose: () => void;
  onRecordPayment?: () => void;
  /** Offered to Manager/Administrator, and only while the invoice can still be
   * corrected. Absent means either "not your role" or "not this invoice" — the
   * note below the totals says which. */
  onEdit?: () => void;
}) {
  const { t } = useI18n();
  // The invoice handed in came from the LIST, and an ERPNext list query cannot
  // return child tables — so its `items` is always empty. Totals looked right
  // because they are stored on the invoice itself; only the lines were missing.
  // Fetch the full document to show them.
  const { token } = useAuth();
  const { data: full } = useQuery({
    queryKey: ["sale", invoice.id],
    queryFn: () => getSale(token as string, invoice.id),
    enabled: !!token && !!invoice.id,
    staleTime: 30_000,
  });
  const lines = full?.items ?? invoice.items;
  const blocked = amendBlockedReason(full ?? invoice);
  const canPay = onRecordPayment && invoice.outstanding_amount > 0;
  const footer =
    onEdit || canPay ? (
      <div className="flex items-center gap-2.5">
        {onEdit && !blocked && (
          <button type="button" onClick={onEdit} className="btn">
            {t("sales.amend.action")}
          </button>
        )}
        {canPay && (
          <button type="button" onClick={onRecordPayment} className="btn btn-filled">
            {t("sales.recordReceipt")}
          </button>
        )}
      </div>
    ) : undefined;
  return (
    <Drawer
      eyebrow={t("sales.drawer.eyebrow")}
      title={invoice.id}
      onClose={onClose}
      width="max-w-[600px]"
      footer={footer}
    >
      <div className="flex justify-between mb-5">
        <div>
          <div className="text-xs muted mb-1">{t("sales.col.customer")}</div>
          <div className="font-medium">{invoice.customer}</div>
        </div>
        <StatusTag label={invoice.status} tone={invoiceTone(invoice.status)} dot={false} />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-6 text-sm">
        <div>
          <div className="text-xs muted mb-1">{t("sales.postingDate")}</div>
          <div>{invoice.posting_date ?? "—"}</div>
        </div>
        <div>
          <div className="text-xs muted mb-1">{t("sales.dueDate")}</div>
          <div>{invoice.due_date ?? "—"}</div>
        </div>
      </div>

      <LineItems items={lines} />

      <div className="flex justify-between py-1.5 text-sm">
        <span className="muted">{t("sales.grandTotal")}</span>
        <span className="font-semibold">{xaf(invoice.grand_total)}</span>
      </div>
      <div className="flex justify-between py-1.5 text-sm">
        <span className="muted">{t("sales.outstanding")}</span>
        <span className="font-semibold">{xaf(invoice.outstanding_amount)}</span>
      </div>

      {invoice.amended_from && (
        <div className="mt-4 text-[13px] muted">
          {t("sales.amend.replaces").replace("{id}", invoice.amended_from)}
        </div>
      )}

      {onEdit && blocked && (
        <div className="mt-4 text-[13px] muted">
          {t(blocked === "opening" ? "sales.amend.blockedOpening" : "sales.amend.blockedSettled")}
        </div>
      )}

      {invoice.remarks && (
        <div className="mt-5">
          <div className="text-[11px] tracking-[0.08em] uppercase muted mb-1.5">{t("sales.remarks")}</div>
          <div className="text-sm">{invoice.remarks}</div>
        </div>
      )}
    </Drawer>
  );
}

function LineItems({ items }: { items: SalesInvoice["items"] }) {
  const { t } = useI18n();
  return (
    <>
      <div className="text-[11px] tracking-[0.08em] uppercase muted mb-2">{t("sales.lineItems")}</div>
      <div className="blueprint p-0 overflow-hidden mb-5">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="muted">
              <th className="text-left text-[11px] uppercase font-semibold px-3 py-2 border-b border-divider">
                {t("sales.col.item")}
              </th>
              <th className="text-right text-[11px] uppercase font-semibold px-3 py-2 border-b border-divider">
                {t("sales.col.qty")}
              </th>
              <th className="text-right text-[11px] uppercase font-semibold px-3 py-2 border-b border-divider">
                {t("sales.col.amount")}
              </th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-3 py-4 text-center muted-2">
                  {t("sales.noLineItems")}
                </td>
              </tr>
            ) : (
              items.map((it, i) => (
                <tr key={i} className="border-b border-solid divide-soft">
                  <td className="px-3 py-2">
                    <div className="font-medium">{it.item_name || it.item_code}</div>
                    {it.item_name && (
                      <div className="text-xs muted-2 mt-0.5">{it.item_code}</div>
                    )}
                  </td>
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
