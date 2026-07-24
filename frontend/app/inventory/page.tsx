"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ConfirmDialog from "@/components/ConfirmDialog";
import BatchDialog from "@/components/inventory/BatchDialog";
import GoodsMovementDialog from "@/components/inventory/GoodsMovementDialog";
import WarehouseDialog from "@/components/inventory/WarehouseDialog";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import StatusTag, { ActiveTag, type Tone } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { UnauthorizedError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type Batch,
  type BatchInput,
  type MovementInput,
  type Warehouse,
  type WarehouseInput,
  createBatch,
  createWarehouse,
  deleteWarehouse,
  issueGoods,
  listBatches,
  listStock,
  listWarehouses,
  receiveGoods,
  updateWarehouse,
} from "@/lib/inventory";

type Tab = "stock" | "warehouses" | "batches";
const TABS: { key: Tab; label: string }[] = [
  { key: "stock", label: "Stock" },
  { key: "warehouses", label: "Warehouses" },
  { key: "batches", label: "Batches" },
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
        <span>Operations</span>
        <span>›</span>
        <span className="text-ink">Inventory</span>
      </nav>
      <div className="mb-5">
        <h1 className="text-[32px] mb-1">Inventory</h1>
        <p className="muted text-sm m-0">
          Stock levels, warehouses and batch tracking
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-divider mb-5">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`relative px-4 py-2.5 text-sm font-heading font-semibold -mb-px ${
              tab === t.key ? "text-ink" : "muted hover:text-ink"
            }`}
          >
            {t.label}
            {tab === t.key && (
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
function stockStatus(qty: number): { label: string; tone: Tone } {
  if (qty <= 0) return { label: "Out", tone: "err" };
  if (qty <= 10) return { label: "Low", tone: "warn" };
  return { label: "In stock", tone: "ok" };
}

function StockTab({ token, warehouses }: { token: string; warehouses: Warehouse[] }) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [warehouseFilter, setWarehouseFilter] = useState("");
  const [movement, setMovement] = useState<"receive" | "issue" | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const move = useMutation({
    mutationFn: (input: MovementInput) =>
      movement === "receive" ? receiveGoods(token, input) : issueGoods(token, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stock"] });
      setMovement(null);
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <div className="relative w-full sm:w-[320px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3">
            <Icon name="search" size={15} />
          </span>
          <input
            className="eq-field w-full h-[38px] pl-8 pr-3 text-sm"
            placeholder="Filter by product SKU…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={warehouseFilter}
          onChange={(e) => setWarehouseFilter(e.target.value)}
        >
          <option value="">All warehouses</option>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => {
            setError(null);
            setMovement("issue");
          }}
          className="h-[38px] px-3.5 inline-flex items-center gap-2 rounded-lg border border-divider text-sm font-heading font-semibold hover:bg-[color-mix(in_srgb,var(--color-text)_7%,transparent)]"
        >
          Issue
        </button>
        <button
          type="button"
          onClick={() => {
            setError(null);
            setMovement("receive");
          }}
          className="h-[38px] px-3.5 inline-flex items-center gap-2 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
        >
          <Icon name="plus" size={15} sw={1.8} />
          Receive
        </button>
      </div>

      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[820px]">
            <thead>
              <tr className="muted">
                {["Product", "Warehouse", "Actual", "Reserved", "Projected", "Status"].map(
                  (h, i) => (
                    <th
                      key={h}
                      className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${
                        i === 0 ? "text-left pl-5" : "text-left"
                      } ${["Actual", "Reserved", "Projected"].includes(h) ? "!text-right" : ""}`}
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <TableSkeleton cols={6} />
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center muted-2">
                    No stock records.
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
                        <StatusTag label={st.label} tone={st.tone} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Blueprint>

      {movement && (
        <GoodsMovementDialog
          mode={movement}
          warehouses={warehouses}
          busy={move.isPending}
          error={error}
          onCancel={() => setMovement(null)}
          onSubmit={(input) => {
            setError(null);
            move.mutate(input);
          }}
        />
      )}
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
          className="h-[38px] px-3.5 inline-flex items-center gap-2 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
        >
          <Icon name="plus" size={15} sw={1.8} />
          New warehouse
        </button>
      </div>
      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[720px]">
            <thead>
              <tr className="muted">
                {["Warehouse", "Parent", "Type", "Status", ""].map((h, i) => (
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
                <tr><td colSpan={5} className="py-12 text-center muted-2">No warehouses yet.</td></tr>
              ) : (
                warehouses.map((w) => (
                  <tr key={w.id} className="group border-b border-solid divide-soft hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
                    <td className="pl-5 py-3 font-medium">{w.name}</td>
                    <td className="py-3 muted">{w.parent_warehouse ?? "—"}</td>
                    <td className="py-3 muted">{w.is_group ? "Group" : "Storage"}</td>
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
          title="Delete warehouse"
          message={`Delete “${dialog.w.name}”? This cannot be undone.`}
          confirmLabel="Delete"
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
          className="h-[38px] px-3.5 inline-flex items-center gap-2 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
        >
          <Icon name="plus" size={15} sw={1.8} />
          New batch
        </button>
      </div>
      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[720px]">
            <thead>
              <tr className="muted">
                {["Batch", "Product", "Expiry", "Manufactured", "Qty"].map((h, i) => (
                  <th key={h} className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${i === 0 ? "text-left pl-5" : "text-left"} ${h === "Qty" ? "!text-right pr-5" : ""}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <TableSkeleton cols={5} />
              ) : (data ?? []).length === 0 ? (
                <tr><td colSpan={5} className="py-12 text-center muted-2">No batches yet.</td></tr>
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
