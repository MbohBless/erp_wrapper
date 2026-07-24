"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import BillDialog from "@/components/purchases/BillDialog";
import BillDrawer from "@/components/purchases/BillDrawer";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import StatusTag, { invoiceTone } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useDebounced } from "@/components/ui/hooks";
import { UnauthorizedError, shortDate, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type PurchaseInput,
  type PurchaseInvoice,
  createPurchase,
  listPurchases,
} from "@/lib/purchases";

export default function PurchasesPage() {
  return (
    <AppShell>
      <PurchasesContent />
    </AppShell>
  );
}


function PurchasesContent() {
  const { token, logout } = useAuth();
  const qc = useQueryClient();
  const [searchInput, setSearchInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [creating, setCreating] = useState(false);
  const [viewing, setViewing] = useState<PurchaseInvoice | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const search = useDebounced(searchInput);

  const { data, isLoading, error } = useQuery({
    queryKey: ["purchases", search],
    queryFn: () => listPurchases(token as string, { search: search || undefined }),
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

  const createMut = useMutation({
    mutationFn: (input: PurchaseInput) => createPurchase(token as string, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["purchases"] });
      setCreating(false);
    },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>EquiMed</span>
        <span>›</span>
        <span className="text-ink">Purchases</span>
      </nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-5">
        <div>
          <h1 className="text-[32px] mb-1">Purchases</h1>
          <p className="muted text-sm m-0">Supplier bills and goods received</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setFormError(null);
            setCreating(true);
          }}
          className="h-10 px-4 inline-flex items-center gap-2 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
        >
          <Icon name="plus" size={15} sw={1.8} />
          New purchase
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <div className="relative w-full sm:w-[340px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3">
            <Icon name="search" size={15} />
          </span>
          <input
            className="eq-field w-full h-[38px] pl-8 pr-3 text-sm"
            placeholder="Filter by supplier…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="Paid">Paid</option>
          <option value="Unpaid">Unpaid</option>
          <option value="Overdue">Overdue</option>
        </select>
      </div>

      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[800px]">
            <thead>
              <tr className="muted">
                {["Bill", "Supplier", "Date", "Amount", "Status", ""].map((h, i) => (
                  <th
                    key={i}
                    className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${
                      i === 0 ? "text-left pl-5" : "text-left"
                    } ${h === "Amount" ? "!text-right" : ""}`}
                  >
                    {h}
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
                    Could not load purchases.
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center muted-2">
                    No purchases match your filters.
                  </td>
                </tr>
              ) : (
                rows.map((bill) => (
                  <tr
                    key={bill.id}
                    className="group border-b border-solid divide-soft hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]"
                  >
                    <td className="pl-5 py-3 font-heading tracking-wide">{bill.id}</td>
                    <td className="py-3 font-medium">{bill.supplier}</td>
                    <td className="py-3 muted">{shortDate(bill.posting_date)}</td>
                    <td className="py-3 text-right font-semibold">
                      {xaf(bill.grand_total)}
                    </td>
                    <td className="py-3">
                      <StatusTag label={bill.status} tone={invoiceTone(bill.status)} />
                    </td>
                    <td className="py-3 pr-4">
                      <RowActions onView={() => setViewing(bill)} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Blueprint>

      {creating && (
        <BillDialog
          token={token as string}
          busy={createMut.isPending}
          error={formError}
          onCancel={() => setCreating(false)}
          onSubmit={(input) => {
            setFormError(null);
            createMut.mutate(input);
          }}
        />
      )}
      {viewing && <BillDrawer bill={viewing} onClose={() => setViewing(null)} />}
    </div>
  );
}

