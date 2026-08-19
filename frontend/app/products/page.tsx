"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ConfirmDialog from "@/components/ConfirmDialog";
import ProductDrawer from "@/components/products/ProductDrawer";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import { ActiveTag } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import Pagination from "@/components/ui/Pagination";
import { useDebounced, usePaged } from "@/components/ui/hooks";
import { useReferenceOptions } from "@/lib/reference";
import { UnauthorizedError, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useAppName } from "@/lib/branding";
import {
  type Product,
  deleteProduct,
  listProducts,
} from "@/lib/products";

export default function ProductsPage() {
  return (
    <AppShell>
      <ProductsContent />
    </AppShell>
  );
}


type Dialog =
  | { kind: "view"; product: Product }
  | { kind: "delete"; product: Product }
  | null;

function ProductsContent() {
  const appName = useAppName();
  const { token, logout } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const qc = useQueryClient();

  const [searchInput, setSearchInput] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const search = useDebounced(searchInput);
  const paged = usePaged([search, categoryFilter, statusFilter]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["products", search, categoryFilter, statusFilter, paged.page],
    queryFn: () =>
      listProducts(token as string, {
        search: search || undefined,
        category: categoryFilter || undefined,
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

  // The category list comes from the reference endpoint, not from the rows
  // on screen. Derived from the page, the dropdown would only ever offer
  // the categories that happened to appear on it — so filtering to one
  // would become impossible the moment its products fell to page two.
  const { options } = useReferenceOptions();
  const categories = options?.item_groups ?? [];

  const rows = useMemo(() => (data ?? []).slice(0, paged.size), [data, paged.size]);
  const hasNext = (data?.length ?? 0) > paged.size;

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteProduct(token as string, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["products"] });
      setDialog(null);
    },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });

  const openEdit = (product: Product) =>
    router.push(`/products/${encodeURIComponent(product.id)}/edit`);

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>{appName}</span>
        <span>›</span>
        <span className="text-ink">{t("products.title")}</span>
      </nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-5">
        <div>
          <h1 className="text-[32px] mb-1">{t("products.title")}</h1>
          <p className="muted text-sm m-0">{t("products.subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => router.push("/products/new")}
          className="btn btn-filled"
        >
          <Icon name="plus" size={15} sw={1.8} />
          {t("products.new")}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <div className="relative w-full sm:w-[340px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3">
            <Icon name="search" size={15} />
          </span>
          <input
            className="eq-field w-full h-[38px] pl-8 pr-3 text-sm"
            placeholder={t("products.filterPlaceholder")}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
        >
          <option value="">{t("products.allCategories")}</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">{t("products.allStatuses")}</option>
          <option value="active">{t("common.active")}</option>
          <option value="disabled">{t("common.disabled")}</option>
        </select>
      </div>

      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[880px]">
            <thead>
              <tr className="muted">
                {[
                  { label: t("products.colProduct") },
                  { label: t("products.colSku") },
                  { label: t("products.colCategory") },
                  { label: t("products.colUnit") },
                  { label: t("products.selling"), right: true },
                  { label: t("common.status") },
                  { label: "" },
                ].map((h, i) => (
                  <th
                    key={i}
                    className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${
                      i === 0 ? "text-left pl-5" : "text-left"
                    } ${h.right ? "!text-right pr-5" : ""}`}
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
                    {t("products.loadError")}
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center muted-2">
                    {t("products.empty")}
                  </td>
                </tr>
              ) : (
                rows.map((p) => (
                  <tr
                    key={p.id}
                    className="group border-b border-solid divide-soft hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]"
                  >
                    <td className="pl-5 py-3 font-medium">{p.name}</td>
                    <td className="py-3 muted">{p.sku}</td>
                    <td className="py-3 muted">{p.category}</td>
                    <td className="py-3 muted">{p.unit}</td>
                    <td className="py-3 pr-5 text-right font-semibold">
                      {p.selling_price != null ? xaf(p.selling_price) : "—"}
                    </td>
                    <td className="py-3">
                      <ActiveTag disabled={p.disabled} />
                    </td>
                    <td className="py-3 pr-4">
                      <RowActions
                        onView={() => setDialog({ kind: "view", product: p })}
                        onEdit={() => openEdit(p)}
                        onDelete={() => {
                          setFormError(null);
                          setDialog({ kind: "delete", product: p });
                        }}
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
        <ProductDrawer
          product={dialog.product}
          onClose={() => setDialog(null)}
          onEdit={() => openEdit(dialog.product)}
        />
      )}

      {dialog?.kind === "delete" && (
        <ConfirmDialog
          title={t("products.deleteTitle")}
          message={`${t("action.delete")} “${dialog.product.name}” — ${t("common.deleteConfirm")}`}
          confirmLabel={t("action.delete")}
          busy={deleteMut.isPending}
          error={formError}
          onCancel={() => setDialog(null)}
          onConfirm={() => deleteMut.mutate(dialog.product.id)}
        />
      )}
    </div>
  );
}

