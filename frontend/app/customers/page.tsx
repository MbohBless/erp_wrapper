"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ConfirmDialog from "@/components/ConfirmDialog";
import CustomerDrawer from "@/components/customers/CustomerDrawer";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import { ActiveTag } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useDebounced } from "@/components/ui/hooks";
import { UnauthorizedError, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { type Customer, deleteCustomer, listCustomers } from "@/lib/customers";
import { useI18n } from "@/lib/i18n";
import { useAppName } from "@/lib/branding";

export default function CustomersPage() {
  return (
    <AppShell>
      <CustomersContent />
    </AppShell>
  );
}

type Dialog =
  | { kind: "view"; customer: Customer }
  | { kind: "delete"; customer: Customer }
  | null;

function CustomersContent() {
  const appName = useAppName();
  const { token, logout } = useAuth();
  const { t } = useI18n();
  const qc = useQueryClient();
  const router = useRouter();

  const [searchInput, setSearchInput] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState(""); // "", "active", "disabled"
  const [dialog, setDialog] = useState<Dialog>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const search = useDebounced(searchInput);

  const { data, isLoading, error } = useQuery({
    queryKey: ["customers", search, typeFilter],
    queryFn: () =>
      listCustomers(token as string, {
        search: search || undefined,
        customer_type: typeFilter || undefined,
      }),
    enabled: !!token,
  });

  useEffect(() => {
    if (error instanceof UnauthorizedError) logout();
  }, [error, logout]);

  const rows = useMemo(() => {
    const list = data ?? [];
    if (statusFilter === "active") return list.filter((c) => !c.disabled);
    if (statusFilter === "disabled") return list.filter((c) => c.disabled);
    return list;
  }, [data, statusFilter]);

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteCustomer(token as string, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customers"] });
      setDialog(null);
    },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });

  function goEdit(customer: Customer) {
    router.push(`/customers/${encodeURIComponent(customer.id)}/edit`);
  }

  return (
    <div className="eq-view">
      {/* Header */}
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>{appName}</span>
        <span>›</span>
        <span className="text-ink">{t("customers.title")}</span>
      </nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-5">
        <div>
          <h1 className="text-[32px] mb-1">{t("customers.title")}</h1>
          <p className="muted text-sm m-0">
            {t("customers.subtitle")}
          </p>
        </div>
        <button
          type="button"
          onClick={() => router.push("/customers/new")}
          className="btn btn-filled"
        >
          <Icon name="plus" size={15} sw={1.8} />
          {t("customers.new")}
        </button>
      </div>

      {/* Search + filters */}
      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <div className="relative w-full sm:w-[340px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3">
            <Icon name="search" size={15} />
          </span>
          <input
            className="eq-field w-full h-[38px] pl-8 pr-3 text-sm"
            placeholder={t("customers.searchPlaceholder")}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">{t("customers.filter.allTypes")}</option>
          <option value="Company">{t("customers.type.company")}</option>
          <option value="Individual">{t("customers.type.individual")}</option>
        </select>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">{t("customers.filter.allStatuses")}</option>
          <option value="active">{t("common.active")}</option>
          <option value="disabled">{t("common.disabled")}</option>
        </select>
      </div>

      {/* Table */}
      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[860px]">
            <thead>
              <tr className="muted">
                {[
                  { k: "account", label: t("customers.col.account") },
                  { k: "type", label: t("customers.col.type") },
                  { k: "contact", label: t("customers.col.contact") },
                  { k: "group", label: t("customers.col.group") },
                  { k: "balance", label: t("customers.col.balance") },
                  { k: "status", label: t("common.status") },
                  { k: "actions", label: "" },
                ].map((h, i) => (
                  <th
                    key={i}
                    className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${
                      i === 0 ? "text-left pl-5" : "text-left"
                    } ${h.k === "balance" ? "!text-right pr-5" : ""}`}
                  >
                    {h.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <TableSkeleton cols={7} />
              ) : error ? (
                <tr>
                  <td colSpan={7} className="py-10 text-center muted">
                    {t("customers.loadError")}
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center muted-2">
                    {t("customers.empty")}
                  </td>
                </tr>
              ) : (
                rows.map((c) => (
                  <tr
                    key={c.id}
                    className="group border-b border-solid divide-soft hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]"
                  >
                    <td className="pl-5 py-3 font-medium">{c.name}</td>
                    <td className="py-3 muted">{c.customer_type}</td>
                    <td className="py-3 muted">
                      {c.contact_person || c.phone || "—"}
                    </td>
                    <td className="py-3 muted">{c.customer_group}</td>
                    <td className="py-3 pr-5 text-right font-semibold">
                      {c.outstanding_balance != null
                        ? xaf(c.outstanding_balance)
                        : "—"}
                    </td>
                    <td className="py-3">
                      <ActiveTag disabled={c.disabled} />
                    </td>
                    <td className="py-3 pr-4">
                      <RowActions
                        onView={() => setDialog({ kind: "view", customer: c })}
                        onEdit={() => goEdit(c)}
                        onDelete={() => {
                          setFormError(null);
                          setDialog({ kind: "delete", customer: c });
                        }}
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Blueprint>

      {/* Dialogs */}
      {dialog?.kind === "view" && (
        <CustomerDrawer
          customer={dialog.customer}
          onClose={() => setDialog(null)}
          onEdit={() => goEdit(dialog.customer)}
        />
      )}

      {dialog?.kind === "delete" && (
        <ConfirmDialog
          title={t("customers.delete.title")}
          message={`${t("customers.delete.question").replace("{name}", dialog.customer.name)} ${t("common.deleteConfirm")}`}
          confirmLabel={t("action.delete")}
          busy={deleteMut.isPending}
          error={formError}
          onCancel={() => setDialog(null)}
          onConfirm={() => deleteMut.mutate(dialog.customer.id)}
        />
      )}
    </div>
  );
}
