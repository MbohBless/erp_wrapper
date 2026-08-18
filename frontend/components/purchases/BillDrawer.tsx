"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/lib/auth";
import { getPurchase } from "@/lib/purchases";

import Drawer from "@/components/ui/Drawer";
import StatusTag, { invoiceTone } from "@/components/ui/StatusTag";
import { xaf } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { amendBlockedReason, type PurchaseInvoice } from "@/lib/purchases";

export default function BillDrawer({
  bill,
  onClose,
  onRecordPayment,
  onEdit,
}: {
  bill: PurchaseInvoice;
  onClose: () => void;
  onRecordPayment?: () => void;
  /** Manager/Administrator only, and only while the bill can still be
   * corrected. See the sales drawer. */
  onEdit?: () => void;
}) {
  const { t } = useI18n();
  // Same as the sales drawer: the bill came from the list, whose items are
  // never populated because ERPNext list queries omit child tables.
  const { token } = useAuth();
  const { data: full } = useQuery({
    queryKey: ["purchase", bill.id],
    queryFn: () => getPurchase(token as string, bill.id),
    enabled: !!token && !!bill.id,
    staleTime: 30_000,
  });
  const lines = full?.items ?? bill.items;
  const blocked = amendBlockedReason(full ?? bill);
  const canPay = onRecordPayment && bill.outstanding_amount > 0;
  const footer =
    onEdit || canPay ? (
      <div className="flex items-center gap-2.5">
        {onEdit && !blocked && (
          <button type="button" onClick={onEdit} className="btn">
            {t("purchases.amend.action")}
          </button>
        )}
        {canPay && (
          <button type="button" onClick={onRecordPayment} className="btn btn-filled">
            {t("purchases.recordPayment")}
          </button>
        )}
      </div>
    ) : undefined;
  return (
    <Drawer
      eyebrow={t("purchases.drawer.eyebrow")}
      title={bill.id}
      onClose={onClose}
      width="max-w-[600px]"
      footer={footer}
    >
      <div className="flex justify-between mb-5">
        <div>
          <div className="text-xs muted mb-1">{t("purchases.col.supplier")}</div>
          <div className="font-medium">{bill.supplier}</div>
        </div>
        <StatusTag label={bill.status} tone={invoiceTone(bill.status)} dot={false} />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-6 text-sm">
        <div>
          <div className="text-xs muted mb-1">{t("purchases.postingDate")}</div>
          <div>{bill.posting_date ?? "—"}</div>
        </div>
        <div>
          <div className="text-xs muted mb-1">{t("purchases.supplierBillNo")}</div>
          <div>{bill.bill_no ?? "—"}</div>
        </div>
      </div>

      <div className="text-[11px] tracking-[0.08em] uppercase muted mb-2">{t("purchases.lineItems")}</div>
      <div className="blueprint p-0 overflow-hidden mb-5">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="muted">
              <th className="text-left text-[11px] uppercase font-semibold px-3 py-2 border-b border-divider">
                {t("purchases.col.item")}
              </th>
              <th className="text-right text-[11px] uppercase font-semibold px-3 py-2 border-b border-divider">
                {t("purchases.col.qty")}
              </th>
              <th className="text-right text-[11px] uppercase font-semibold px-3 py-2 border-b border-divider">
                {t("purchases.col.amount")}
              </th>
            </tr>
          </thead>
          <tbody>
            {lines.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-3 py-4 text-center muted-2">
                  {t("purchases.noLineItems")}
                </td>
              </tr>
            ) : (
              lines.map((it, i) => (
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

      <div className="flex justify-between py-1.5 text-sm">
        <span className="muted">{t("purchases.grandTotal")}</span>
        <span className="font-semibold">{xaf(bill.grand_total)}</span>
      </div>
      <div className="flex justify-between py-1.5 text-sm">
        <span className="muted">{t("purchases.outstanding")}</span>
        <span className="font-semibold">{xaf(bill.outstanding_amount)}</span>
      </div>

      {bill.amended_from && (
        <div className="mt-4 text-[13px] muted">
          {t("purchases.amend.replaces").replace("{id}", bill.amended_from)}
        </div>
      )}

      {onEdit && blocked && (
        <div className="mt-4 text-[13px] muted">
          {t(blocked === "opening" ? "purchases.amend.blockedOpening" : "purchases.amend.blockedSettled")}
        </div>
      )}

      {bill.remarks && (
        <div className="mt-5">
          <div className="text-[11px] tracking-[0.08em] uppercase muted mb-1.5">{t("purchases.remarks")}</div>
          <div className="text-sm">{bill.remarks}</div>
        </div>
      )}
    </Drawer>
  );
}
