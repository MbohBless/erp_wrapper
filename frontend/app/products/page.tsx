"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ConfirmDialog from "@/components/ConfirmDialog";
import ProductDialog from "@/components/products/ProductDialog";
import ProductDrawer from "@/components/products/ProductDrawer";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import { ActiveTag } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useDebounced } from "@/components/ui/hooks";
import { UnauthorizedError, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type Product,
  type ProductInput,
  createProduct,
  deleteProduct,
  listProducts,
  updateProduct,
} from "@/lib/products";

export default function ProductsPage() {
  return (
    <AppShell>
      <ProductsContent />
    </AppShell>
  );
}


type Dialog =
  | { kind: "create" }
  | { kind: "edit"; product: Product }
  | { kind: "view"; product: Product }
  | { kind: "delete"; product: Product }
  | null;

function ProductsContent() {
  const { token, logout } = useAuth();
  const qc = useQueryClient();

  const [searchInput, setSearchInput] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const search = useDebounced(searchInput);

  const { data, isLoading, error } = useQuery({
    queryKey: ["products", search],
    queryFn: () => listProducts(token as string, { search: search || undefined }),
    enabled: !!token,
  });

  useEffect(() => {
    if (error instanceof UnauthorizedError) logout();
  }, [error, logout]);

  const categories = useMemo(
    () => Array.from(new Set((data ?? []).map((p) => p.category))).sort(),
    [data]
  );

  const rows = useMemo(() => {
    let list = data ?? [];
    if (categoryFilter) list = list.filter((p) => p.category === categoryFilter);
    if (statusFilter === "active") list = list.filter((p) => !p.disabled);
    if (statusFilter === "disabled") list = list.filter((p) => p.disabled);
    return list;
  }, [data, categoryFilter, statusFilter]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["products"] });

  const createMut = useMutation({
    mutationFn: (input: ProductInput) => createProduct(token as string, input),
    onSuccess: () => {
      invalidate();
      setDialog(null);
    },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, input }: { id: string; input: ProductInput }) =>
      updateProduct(token as string, id, input),
    onSuccess: () => {
      invalidate();
      setDialog(null);
    },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteProduct(token as string, id),
    onSuccess: () => {
      invalidate();
      setDialog(null);
    },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });

  function openCreate() {
    setFormError(null);
    setDialog({ kind: "create" });
  }
  function openEdit(product: Product) {
    setFormError(null);
    setDialog({ kind: "edit", product });
  }

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>EquiMed</span>
        <span>›</span>
        <span className="text-ink">Products</span>
      </nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-5">
        <div>
          <h1 className="text-[32px] mb-1">Products</h1>
          <p className="muted text-sm m-0">Catalogue of medical equipment &amp; supplies</p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="h-10 px-4 inline-flex items-center gap-2 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
        >
          <Icon name="plus" size={15} sw={1.8} />
          New product
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <div className="relative w-full sm:w-[340px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3">
            <Icon name="search" size={15} />
          </span>
          <input
            className="eq-field w-full h-[38px] pl-8 pr-3 text-sm"
            placeholder="Filter products…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
        >
          <option value="">All categories</option>
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
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
        </select>
      </div>

      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[880px]">
            <thead>
              <tr className="muted">
                {["Product", "SKU", "Category", "Unit", "Selling", "Status", ""].map(
                  (h, i) => (
                    <th
                      key={i}
                      className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${
                        i === 0 ? "text-left pl-5" : "text-left"
                      } ${h === "Selling" ? "!text-right pr-5" : ""}`}
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <TableSkeleton cols={7} />
              ) : error ? (
                <tr>
                  <td colSpan={7} className="py-10 text-center muted">
                    Could not load products.
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center muted-2">
                    No products match your filters.
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
      </Blueprint>

      {(dialog?.kind === "create" || dialog?.kind === "edit") && (
        <ProductDialog
          initial={dialog.kind === "edit" ? dialog.product : null}
          busy={createMut.isPending || updateMut.isPending}
          error={formError}
          onCancel={() => setDialog(null)}
          onSubmit={(input) => {
            setFormError(null);
            if (dialog.kind === "edit") {
              updateMut.mutate({ id: dialog.product.id, input });
            } else {
              createMut.mutate(input);
            }
          }}
        />
      )}

      {dialog?.kind === "view" && (
        <ProductDrawer
          product={dialog.product}
          onClose={() => setDialog(null)}
          onEdit={() => openEdit(dialog.product)}
        />
      )}

      {dialog?.kind === "delete" && (
        <ConfirmDialog
          title="Delete product"
          message={`Delete “${dialog.product.name}”? This cannot be undone.`}
          confirmLabel="Delete"
          busy={deleteMut.isPending}
          error={formError}
          onCancel={() => setDialog(null)}
          onConfirm={() => deleteMut.mutate(dialog.product.id)}
        />
      )}
    </div>
  );
}

