"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import PaymentDialog, { type PaymentValue } from "@/components/finance/PaymentDialog";
import InvoiceDrawer from "@/components/sales/InvoiceDrawer";
import { recordReceipt } from "@/lib/payments";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import StatusTag, { invoiceTone } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useDebounced } from "@/components/ui/hooks";
import { UnauthorizedError, shortDate, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { type SalesInvoice, listSales } from "@/lib/sales";

export default function SalesPage() {
  return (
    <AppShell>
      <SalesContent />
    </AppShell>
  );
}


function SalesContent() {
  const { t } = useI18n();
  const { token, logout } = useAuth();
  const qc = useQueryClient();
  const router = useRouter();
  const [searchInput, setSearchInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [viewing, setViewing] = useState<SalesInvoice | null>(null);
  const [paying, setPaying] = useState<SalesInvoice | null>(null);
  const [payError, setPayError] = useState<string | null>(null);

  const search = useDebounced(searchInput);

  const { data, isLoading, error } = useQuery({
    queryKey: ["sales", search],
    queryFn: () => listSales(token as string, { search: search || undefined }),
    enabled: !!token,
  });

  useEffect(() => {
    if (error instanceof UnauthorizedError) logout();
  }, [error, logout]);

  const rows = useMemo(() => {
    let list = data ?? [];
    if (statusFilter)
      list = list.filter((i) =>
        i.status.toLowerCase().includes(statusFilter.toLowerCase())
      );
    return list;
  }, [data, statusFilter]);

  const payMut = useMutation({
    mutationFn: (v: PaymentValue) =>
      recordReceipt(token as string, {
        invoice_id: (paying as SalesInvoice).id,
        amount: v.amount ?? undefined,
        mode_of_payment: v.mode_of_payment,
        posting_date: v.posting_date,
        reference_no: v.reference_no,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sales"] });
      setPaying(null);
      setViewing(null);
    },
    onError: (e) => setPayError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>EquiMed</span>
        <span>›</span>
        <span className="text-ink">{t("sales.title")}</span>
      </nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-5">
        <div>
          <h1 className="text-[32px] mb-1">{t("sales.title")}</h1>
          <p className="muted text-sm m-0">
            {t("sales.subtitle")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => router.push("/sales/new")}
          className="btn btn-filled"
        >
          <Icon name="plus" size={15} sw={1.8} />
          {t("sales.newInvoice")}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <div className="relative w-full sm:w-[340px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3">
            <Icon name="search" size={15} />
          </span>
          <input
            className="eq-field w-full h-[38px] pl-8 pr-3 text-sm"
            placeholder={t("sales.filterCustomer")}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">{t("sales.allStatuses")}</option>
          <option value="Paid">{t("sales.status.paid")}</option>
          <option value="Unpaid">{t("sales.status.unpaid")}</option>
          <option value="Overdue">{t("sales.status.overdue")}</option>
        </select>
      </div>

      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[760px]">
            <thead>
              <tr className="muted">
                {[
                  { label: t("sales.col.invoice"), right: false },
                  { label: t("sales.col.customer"), right: false },
                  { label: t("sales.col.date"), right: false },
                  { label: t("sales.col.amount"), right: true },
                  { label: t("common.status"), right: false },
                  { label: "", right: false },
                ].map((h, i) => (
                  <th
                    key={i}
                    className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${
                      i === 0 ? "text-left pl-5" : "text-left"
                    } ${h.right ? "!text-right" : ""}`}
                  >
                    {h.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <TableSkeleton cols={6} />
              ) : error ? (
                <tr>
                  <td colSpan={6} className="py-10 text-center muted">
                    {t("sales.loadError")}
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center muted-2">
                    {t("sales.empty")}
                  </td>
                </tr>
              ) : (
                rows.map((inv) => (
                  <tr
                    key={inv.id}
                    className="group border-b border-solid divide-soft hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]"
                  >
                    <td className="pl-5 py-3 font-heading tracking-wide">{inv.id}</td>
                    <td className="py-3 font-medium">{inv.customer}</td>
                    <td className="py-3 muted">{shortDate(inv.posting_date)}</td>
                    <td className="py-3 text-right font-semibold">
                      {xaf(inv.grand_total)}
                    </td>
                    <td className="py-3">
                      <StatusTag label={inv.status} tone={invoiceTone(inv.status)} />
                    </td>
                    <td className="py-3 pr-4">
                      <RowActions onView={() => setViewing(inv)} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Blueprint>

      {viewing && (
        <InvoiceDrawer
          invoice={viewing}
          onClose={() => setViewing(null)}
          onRecordPayment={() => {
            setPayError(null);
            setPaying(viewing);
          }}
        />
      )}
      {paying && (
        <PaymentDialog
          mode="receive"
          party={paying.customer}
          reference={paying.id}
          outstanding={paying.outstanding_amount}
          busy={payMut.isPending}
          error={payError}
          onCancel={() => setPaying(null)}
          onSubmit={(v) => {
            setPayError(null);
            payMut.mutate(v);
          }}
        />
      )}
    </div>
  );
}

