"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ConfirmDialog from "@/components/ConfirmDialog";
import SupplierDrawer from "@/components/suppliers/SupplierDrawer";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import { ActiveTag } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import Pagination from "@/components/ui/Pagination";
import { useDebounced, usePaged } from "@/components/ui/hooks";
import { UnauthorizedError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useAppName } from "@/lib/branding";
import {
  type Supplier,
  deleteSupplier,
  listSuppliers,
} from "@/lib/suppliers";

export default function SuppliersPage() {
  return (
    <AppShell>
      <SuppliersContent />
    </AppShell>
  );
}


type Dialog =
  | { kind: "view"; s: Supplier }
  | { kind: "delete"; s: Supplier }
  | null;

function SuppliersContent() {
  const appName = useAppName();
  const { token, logout } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const qc = useQueryClient();
  const [searchInput, setSearchInput] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const search = useDebounced(searchInput);
  const paged = usePaged([search, typeFilter, statusFilter]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["suppliers", search, typeFilter, statusFilter, paged.page],
    queryFn: () =>
      listSuppliers(token as string, {
        search: search || undefined,
        supplier_type: typeFilter || undefined,
        // Active/disabled is decided by ERPNext, not by filtering
        // the fetched page — that would hide every match on the
        // pages the user is not looking at.
        disabled: statusFilter ? statusFilter === "disabled" : undefined,
        limit: paged.fetchLimit,
        start: paged.start,
      }),
    enabled: !!token,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    if (error instanceof UnauthorizedError) logout();
  }, [error, logout]);

  // One row past the page was fetched only to learn whether another
  // page exists; trim it before rendering.
  const rows = useMemo(() => (data ?? []).slice(0, paged.size), [data, paged.size]);
  const hasNext = (data?.length ?? 0) > paged.size;

  const goEdit = (row: Supplier) => router.push(`/suppliers/${encodeURIComponent(row.id)}/edit`);

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteSupplier(token as string, id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["suppliers"] }); setDialog(null); },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>{appName}</span><span>›</span><span className="text-ink">{t("suppliers.title")}</span>
      </nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-5">
        <div>
          <h1 className="text-[32px] mb-1">{t("suppliers.title")}</h1>
          <p className="muted text-sm m-0">{t("suppliers.subtitle")}</p>
        </div>
        <button type="button" onClick={() => router.push("/suppliers/new")} className="btn btn-filled">
          <Icon name="plus" size={15} sw={1.8} />{t("suppliers.new")}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <div className="relative w-full sm:w-[340px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3"><Icon name="search" size={15} /></span>
          <input className="eq-field w-full h-[38px] pl-8 pr-3 text-sm" placeholder={t("suppliers.searchPlaceholder")} value={searchInput} onChange={(e) => setSearchInput(e.target.value)} />
        </div>
        <select className="eq-field h-[38px] px-3 text-sm" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">{t("suppliers.filter.allTypes")}</option><option value="Company">{t("suppliers.type.company")}</option><option value="Individual">{t("suppliers.type.individual")}</option>
        </select>
        <select className="eq-field h-[38px] px-3 text-sm" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">{t("suppliers.filter.allStatuses")}</option><option value="active">{t("common.active")}</option><option value="disabled">{t("common.disabled")}</option>
        </select>
      </div>

      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[820px]">
            <thead>
              <tr className="muted">
                {[t("suppliers.col.supplier"), t("suppliers.col.type"), t("suppliers.col.contact"), t("suppliers.col.leadTime"), t("common.status"), ""].map((h, i) => (
                  <th key={i} className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${i === 0 ? "text-left pl-5" : "text-left"}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <TableSkeleton cols={6} />
              ) : error ? (
                <tr><td colSpan={6} className="py-10 text-center muted">{t("suppliers.loadError")}</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={6} className="py-12 text-center muted-2">{t("suppliers.empty")}</td></tr>
              ) : (
                rows.map((s) => (
                  <tr key={s.id} className="group border-b border-solid divide-soft hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
                    <td className="pl-5 py-3 font-medium">{s.name}</td>
                    <td className="py-3 muted">{s.supplier_type}</td>
                    <td className="py-3 muted">{s.contact_person || s.phone || "—"}</td>
                    <td className="py-3 muted">{s.lead_time_days != null ? `${s.lead_time_days} ${t("suppliers.days")}` : "—"}</td>
                    <td className="py-3"><ActiveTag disabled={s.disabled} /></td>
                    <td className="py-3 pr-4">
                      <RowActions
                        onView={() => setDialog({ kind: "view", s })}
                        onEdit={() => goEdit(s)}
                        onDelete={() => { setFormError(null); setDialog({ kind: "delete", s }); }}
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={paged.page}
          size={paged.size}
          count={rows.length}
          hasNext={hasNext}
          onChange={paged.setPage}
        />
      </Blueprint>

      {dialog?.kind === "view" && (
        <SupplierDrawer supplier={dialog.s} onClose={() => setDialog(null)} onEdit={() => goEdit(dialog.s)} />
      )}
      {dialog?.kind === "delete" && (
        <ConfirmDialog
          title={t("suppliers.delete.title")}
          message={`${t("suppliers.delete.question").replace("{name}", dialog.s.name)} ${t("common.deleteConfirm")}`}
          confirmLabel={t("action.delete")}
          busy={deleteMut.isPending}
          error={formError}
          onCancel={() => setDialog(null)}
          onConfirm={() => deleteMut.mutate(dialog.s.id)}
        />
      )}
    </div>
  );
}
