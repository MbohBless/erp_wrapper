"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ConfirmDialog from "@/components/ConfirmDialog";
import MaintenanceDialog from "@/components/maintenance/MaintenanceDialog";
import MaintenanceDrawer from "@/components/maintenance/MaintenanceDrawer";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import StatusTag, { type Tone } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useDebounced } from "@/components/ui/hooks";
import { UnauthorizedError, shortDate } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type Ticket,
  type TicketInput,
  completeTicket,
  createTicket,
  deleteTicket,
  listTickets,
  updateTicket,
} from "@/lib/maintenance";

const STATUS_TONE: Record<string, Tone> = {
  Completed: "ok",
  "In Progress": "accent",
  Scheduled: "warn",
  Open: "neutral",
  Cancelled: "err",
};

export default function MaintenancePage() {
  return (
    <AppShell>
      <MaintenanceContent />
    </AppShell>
  );
}


type Dialog =
  | { kind: "create" }
  | { kind: "edit"; t: Ticket }
  | { kind: "view"; t: Ticket }
  | { kind: "delete"; t: Ticket }
  | null;

function MaintenanceContent() {
  const { token, logout } = useAuth();
  const qc = useQueryClient();
  const [searchInput, setSearchInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const search = useDebounced(searchInput);

  const { data, isLoading, error } = useQuery({
    queryKey: ["maintenance", search, statusFilter],
    queryFn: () =>
      listTickets(token as string, {
        search: search || undefined,
        status: statusFilter || undefined,
      }),
    enabled: !!token,
  });

  useEffect(() => {
    if (error instanceof UnauthorizedError) logout();
  }, [error, logout]);

  const rows = useMemo(() => data ?? [], [data]);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["maintenance"] });

  const createMut = useMutation({
    mutationFn: (input: TicketInput) => createTicket(token as string, input),
    onSuccess: () => { invalidate(); setDialog(null); },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, input }: { id: string; input: TicketInput }) =>
      updateTicket(token as string, id, input),
    onSuccess: () => { invalidate(); setDialog(null); },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteTicket(token as string, id),
    onSuccess: () => { invalidate(); setDialog(null); },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });
  const completeMut = useMutation({
    mutationFn: (id: string) => completeTicket(token as string, id, { signed: true }),
    onSuccess: (updated) => { invalidate(); setDialog({ kind: "view", t: updated }); },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>EquiMed</span>
        <span>›</span>
        <span className="text-ink">Maintenance</span>
      </nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-5">
        <div>
          <h1 className="text-[32px] mb-1">Maintenance</h1>
          <p className="muted text-sm m-0">Service tickets and field visits</p>
        </div>
        <button
          type="button"
          onClick={() => { setFormError(null); setDialog({ kind: "create" }); }}
          className="h-10 px-4 inline-flex items-center gap-2 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
        >
          <Icon name="plus" size={15} sw={1.8} />
          New ticket
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <div className="relative w-full sm:w-[340px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3">
            <Icon name="search" size={15} />
          </span>
          <input
            className="eq-field w-full h-[38px] pl-8 pr-3 text-sm"
            placeholder="Filter by customer…"
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
          <option value="Open">Open</option>
          <option value="Scheduled">Scheduled</option>
          <option value="In Progress">In Progress</option>
          <option value="Completed">Completed</option>
          <option value="Cancelled">Cancelled</option>
        </select>
      </div>

      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[900px]">
            <thead>
              <tr className="muted">
                {["Ticket", "Equipment", "Customer", "Engineer", "Visit", "Status", ""].map(
                  (h, i) => (
                    <th key={i} className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${i === 0 ? "text-left pl-5" : "text-left"}`}>
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
                <tr><td colSpan={7} className="py-10 text-center muted">Could not load tickets.</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={7} className="py-12 text-center muted-2">No tickets match your filters.</td></tr>
              ) : (
                rows.map((t) => (
                  <tr key={t.id} className="group border-b border-solid divide-soft hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
                    <td className="pl-5 py-3 font-heading tracking-wide">{t.id}</td>
                    <td className="py-3 font-medium">{t.equipment ?? "—"}</td>
                    <td className="py-3 muted">{t.customer}</td>
                    <td className="py-3 muted">{t.engineer ?? "—"}</td>
                    <td className="py-3 muted">{shortDate(t.visit_date)}</td>
                    <td className="py-3">
                      <StatusTag label={t.status} tone={STATUS_TONE[t.status] ?? "neutral"} />
                    </td>
                    <td className="py-3 pr-4">
                      <RowActions
                        onView={() => setDialog({ kind: "view", t })}
                        onEdit={() => { setFormError(null); setDialog({ kind: "edit", t }); }}
                        onDelete={() => { setFormError(null); setDialog({ kind: "delete", t }); }}
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
        <MaintenanceDialog
          initial={dialog.kind === "edit" ? dialog.t : null}
          busy={createMut.isPending || updateMut.isPending}
          error={formError}
          onCancel={() => setDialog(null)}
          onSubmit={(input) => {
            setFormError(null);
            dialog.kind === "edit"
              ? updateMut.mutate({ id: dialog.t.id, input })
              : createMut.mutate(input);
          }}
        />
      )}
      {dialog?.kind === "view" && (
        <MaintenanceDrawer
          ticket={dialog.t}
          completing={completeMut.isPending}
          onClose={() => setDialog(null)}
          onEdit={() => { setFormError(null); setDialog({ kind: "edit", t: dialog.t }); }}
          onComplete={() => completeMut.mutate(dialog.t.id)}
        />
      )}
      {dialog?.kind === "delete" && (
        <ConfirmDialog
          title="Delete ticket"
          message={`Delete ticket “${dialog.t.id}”? This cannot be undone.`}
          confirmLabel="Delete"
          busy={deleteMut.isPending}
          error={formError}
          onCancel={() => setDialog(null)}
          onConfirm={() => deleteMut.mutate(dialog.t.id)}
        />
      )}
    </div>
  );
}

