"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ConfirmDialog from "@/components/ConfirmDialog";
import BatchDialog from "@/components/inventory/BatchDialog";
import WarehouseDialog from "@/components/inventory/WarehouseDialog";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import StatusTag, { ActiveTag, type Tone } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { UnauthorizedError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import {
  type Batch,
  type BatchInput,
  type Warehouse,
  type WarehouseInput,
  createBatch,
  createWarehouse,
  deleteWarehouse,
  listBatches,
  listStock,
  listWarehouses,
  updateWarehouse,
} from "@/lib/inventory";

type Tab = "stock" | "warehouses" | "batches";
const TABS: { key: Tab; labelKey: string }[] = [
  { key: "stock", labelKey: "inventory.tabStock" },
  { key: "warehouses", labelKey: "inventory.tabWarehouses" },
  { key: "batches", labelKey: "inventory.tabBatches" },
];

export default function InventoryPage() {
  return (
    <AppShell>
      <InventoryContent />
    </AppShell>
  );
}

function InventoryContent() {
  const { token, logout } = useAuth();
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("stock");

  const warehousesQ = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => listWarehouses(token as string),
    enabled: !!token,
  });

  useEffect(() => {
    if (warehousesQ.error instanceof UnauthorizedError) logout();
  }, [warehousesQ.error, logout]);

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>EquiMed</span>
        <span>›</span>
        <span>{t("inventory.operations")}</span>
        <span>›</span>
        <span className="text-ink">{t("inventory.title")}</span>
      </nav>
      <div className="mb-5">
        <h1 className="text-[32px] mb-1">{t("inventory.title")}</h1>
        <p className="muted text-sm m-0">
          {t("inventory.subtitle")}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-divider mb-5">
        {TABS.map((tb) => (
          <button
            key={tb.key}
            type="button"
            onClick={() => setTab(tb.key)}
            className={`relative px-4 py-2.5 text-sm font-heading font-semibold -mb-px ${
              tab === tb.key ? "text-ink" : "muted hover:text-ink"
            }`}
          >
            {t(tb.labelKey)}
            {tab === tb.key && (
              <span className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />
            )}
          </button>
        ))}
      </div>

      {tab === "stock" && (
        <StockTab token={token as string} warehouses={warehousesQ.data ?? []} />
      )}
      {tab === "warehouses" && (
        <WarehousesTab token={token as string} warehouses={warehousesQ.data ?? []} loading={warehousesQ.isLoading} />
      )}
      {tab === "batches" && <BatchesTab token={token as string} />}
    </div>
  );
}

// -------------------------------------------------------------- Stock tab
function stockStatus(qty: number): { key: string; tone: Tone } {
  if (qty <= 0) return { key: "inventory.stockOut", tone: "err" };
  if (qty <= 10) return { key: "inventory.stockLow", tone: "warn" };
  return { key: "inventory.stockIn", tone: "ok" };
}

function StockTab({ token, warehouses }: { token: string; warehouses: Warehouse[] }) {
  const { t } = useI18n();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [warehouseFilter, setWarehouseFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["stock"],
    queryFn: () => listStock(token),
  });

  const rows = useMemo(() => {
    let list = data ?? [];
    if (search)
      list = list.filter((s) =>
        s.item_code.toLowerCase().includes(search.toLowerCase())
      );
    if (warehouseFilter) list = list.filter((s) => s.warehouse === warehouseFilter);
    return list;
  }, [data, search, warehouseFilter]);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <div className="relative w-full sm:w-[320px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3">
            <Icon name="search" size={15} />
          </span>
          <input
            className="eq-field w-full h-[38px] pl-8 pr-3 text-sm"
            placeholder={t("inventory.filterSku")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={warehouseFilter}
          onChange={(e) => setWarehouseFilter(e.target.value)}
        >
          <option value="">{t("inventory.allWarehouses")}</option>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => router.push("/inventory/new?mode=issue")}
          className="btn btn-outlined"
        >
          {t("inventory.issue")}
        </button>
        <button
          type="button"
          onClick={() => router.push("/inventory/new?mode=receive")}
          className="btn btn-filled"
        >
          <Icon name="plus" size={15} sw={1.8} />
          {t("inventory.receive")}
        </button>
      </div>

      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[820px]">
            <thead>
              <tr className="muted">
                {[
                  { label: t("inventory.colProduct") },
                  { label: t("inventory.colWarehouse") },
                  { label: t("inventory.colActual"), right: true },
                  { label: t("inventory.colReserved"), right: true },
                  { label: t("inventory.colProjected"), right: true },
                  { label: t("common.status") },
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
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center muted-2">
                    {t("inventory.noStock")}
                  </td>
                </tr>
              ) : (
                rows.map((s, i) => {
                  const st = stockStatus(s.actual_qty);
                  return (
                    <tr key={`${s.item_code}-${s.warehouse}-${i}`} className="border-b border-solid divide-soft">
                      <td className="pl-5 py-3 font-medium">{s.item_code}</td>
                      <td className="py-3 muted">{s.warehouse}</td>
                      <td className="py-3 text-right font-semibold">{s.actual_qty}</td>
                      <td className="py-3 text-right muted">{s.reserved_qty ?? 0}</td>
                      <td className="py-3 text-right muted">{s.projected_qty ?? s.actual_qty}</td>
                      <td className="py-3">
                        <StatusTag label={t(st.key)} tone={st.tone} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Blueprint>
    </div>
  );
}

// --------------------------------------------------------- Warehouses tab
function WarehousesTab({
  token,
  warehouses,
  loading,
}: {
  token: string;
  warehouses: Warehouse[];
  loading: boolean;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [dialog, setDialog] = useState<
    { kind: "create" } | { kind: "edit"; w: Warehouse } | { kind: "delete"; w: Warehouse } | null
  >(null);
  const [error, setError] = useState<string | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["warehouses"] });

  const createMut = useMutation({
    mutationFn: (input: WarehouseInput) => createWarehouse(token, input),
    onSuccess: () => { invalidate(); setDialog(null); },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, input }: { id: string; input: WarehouseInput }) => updateWarehouse(token, id, input),
    onSuccess: () => { invalidate(); setDialog(null); },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteWarehouse(token, id),
    onSuccess: () => { invalidate(); setDialog(null); },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button
          type="button"
          onClick={() => { setError(null); setDialog({ kind: "create" }); }}
          className="btn btn-filled"
        >
          <Icon name="plus" size={15} sw={1.8} />
          {t("inventory.newWarehouse")}
        </button>
      </div>
      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[720px]">
            <thead>
              <tr className="muted">
                {[t("inventory.colWarehouse"), t("inventory.colParent"), t("inventory.colType"), t("common.status"), ""].map((h, i) => (
                  <th key={i} className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${i === 0 ? "text-left pl-5" : "text-left"}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <TableSkeleton cols={5} />
              ) : warehouses.length === 0 ? (
                <tr><td colSpan={5} className="py-12 text-center muted-2">{t("inventory.noWarehouses")}</td></tr>
              ) : (
                warehouses.map((w) => (
                  <tr key={w.id} className="group border-b border-solid divide-soft hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
                    <td className="pl-5 py-3 font-medium">{w.name}</td>
                    <td className="py-3 muted">{w.parent_warehouse ?? "—"}</td>
                    <td className="py-3 muted">{w.is_group ? t("inventory.typeGroup") : t("inventory.typeStorage")}</td>
                    <td className="py-3">
                      <ActiveTag disabled={w.disabled} />
                    </td>
                    <td className="py-3 pr-4">
                      <RowActions
                        onEdit={() => { setError(null); setDialog({ kind: "edit", w }); }}
                        onDelete={() => { setError(null); setDialog({ kind: "delete", w }); }}
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
        <WarehouseDialog
          initial={dialog.kind === "edit" ? dialog.w : null}
          busy={createMut.isPending || updateMut.isPending}
          error={error}
          onCancel={() => setDialog(null)}
          onSubmit={(input) => {
            setError(null);
            dialog.kind === "edit"
              ? updateMut.mutate({ id: dialog.w.id, input })
              : createMut.mutate(input);
          }}
        />
      )}
      {dialog?.kind === "delete" && (
        <ConfirmDialog
          title={t("inventory.deleteWarehouse")}
          message={`${t("action.delete")} “${dialog.w.name}” — ${t("common.deleteConfirm")}`}
          confirmLabel={t("action.delete")}
          busy={deleteMut.isPending}
          error={error}
          onCancel={() => setDialog(null)}
          onConfirm={() => deleteMut.mutate(dialog.w.id)}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------ Batches tab
function BatchesTab({ token }: { token: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["batches"],
    queryFn: () => listBatches(token),
  });

  const createMut = useMutation({
    mutationFn: (input: BatchInput) => createBatch(token, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["batches"] });
      setCreating(false);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button
          type="button"
          onClick={() => { setError(null); setCreating(true); }}
          className="btn btn-filled"
        >
          <Icon name="plus" size={15} sw={1.8} />
          {t("inventory.newBatch")}
        </button>
      </div>
      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[720px]">
            <thead>
              <tr className="muted">
                {[
                  { label: t("inventory.colBatch") },
                  { label: t("inventory.colProduct") },
                  { label: t("inventory.colExpiry") },
                  { label: t("inventory.colManufactured") },
                  { label: t("inventory.colQty"), right: true },
                ].map((h, i) => (
                  <th key={i} className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${i === 0 ? "text-left pl-5" : "text-left"} ${h.right ? "!text-right pr-5" : ""}`}>
                    {h.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <TableSkeleton cols={5} />
              ) : (data ?? []).length === 0 ? (
                <tr><td colSpan={5} className="py-12 text-center muted-2">{t("inventory.noBatches")}</td></tr>
              ) : (
                (data ?? []).map((b: Batch) => (
                  <tr key={b.id} className="border-b border-solid divide-soft">
                    <td className="pl-5 py-3 font-medium font-heading tracking-wide">{b.batch_id}</td>
                    <td className="py-3 muted">{b.item_code}</td>
                    <td className="py-3 muted">{b.expiry_date ?? "—"}</td>
                    <td className="py-3 muted">{b.manufacturing_date ?? "—"}</td>
                    <td className="py-3 pr-5 text-right font-semibold">{b.qty ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Blueprint>

      {creating && (
        <BatchDialog
          busy={createMut.isPending}
          error={error}
          onCancel={() => setCreating(false)}
          onSubmit={(input) => { setError(null); createMut.mutate(input); }}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------- shared bits
