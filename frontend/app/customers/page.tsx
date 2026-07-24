"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ConfirmDialog from "@/components/ConfirmDialog";
import CustomerDialog from "@/components/customers/CustomerDialog";
import CustomerDrawer from "@/components/customers/CustomerDrawer";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import { ActiveTag } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useDebounced } from "@/components/ui/hooks";
import { UnauthorizedError, xaf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  type Customer,
  type CustomerInput,
  createCustomer,
  deleteCustomer,
  listCustomers,
  updateCustomer,
} from "@/lib/customers";

export default function CustomersPage() {
  return (
    <AppShell>
      <CustomersContent />
    </AppShell>
  );
}

type Dialog =
  | { kind: "create" }
  | { kind: "edit"; customer: Customer }
  | { kind: "view"; customer: Customer }
  | { kind: "delete"; customer: Customer }
  | null;

function CustomersContent() {
  const { token, logout } = useAuth();
  const qc = useQueryClient();

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

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["customers"] });

  const createMut = useMutation({
    mutationFn: (input: CustomerInput) => createCustomer(token as string, input),
    onSuccess: () => {
      invalidate();
      setDialog(null);
    },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, input }: { id: string; input: CustomerInput }) =>
      updateCustomer(token as string, id, input),
    onSuccess: () => {
      invalidate();
      setDialog(null);
    },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteCustomer(token as string, id),
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
  function openEdit(customer: Customer) {
    setFormError(null);
    setDialog({ kind: "edit", customer });
  }

  return (
    <div className="eq-view">
      {/* Header */}
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>EquiMed</span>
        <span>›</span>
        <span className="text-ink">Customers</span>
      </nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-5">
        <div>
          <h1 className="text-[32px] mb-1">Customers</h1>
          <p className="muted text-sm m-0">
            Hospital, clinic and pharmacy accounts
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="h-10 px-4 inline-flex items-center gap-2 rounded-lg bg-accent text-bg text-sm font-heading font-semibold hover:bg-accent-600"
        >
          <Icon name="plus" size={15} sw={1.8} />
          New customer
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
            placeholder="Filter customers…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">All types</option>
          <option value="Company">Company</option>
          <option value="Individual">Individual</option>
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

      {/* Table */}
      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[860px]">
            <thead>
              <tr className="muted">
                {["Account", "Type", "Contact", "Group", "Balance", "Status", ""].map(
                  (h, i) => (
                    <th
                      key={i}
                      className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${
                        i === 0 ? "text-left pl-5" : "text-left"
                      } ${h === "Balance" ? "!text-right pr-5" : ""}`}
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
                    Could not load customers.
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center muted-2">
                    No customers match your filters.
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
                        onEdit={() => openEdit(c)}
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
      {(dialog?.kind === "create" || dialog?.kind === "edit") && (
        <CustomerDialog
          initial={dialog.kind === "edit" ? dialog.customer : null}
          busy={createMut.isPending || updateMut.isPending}
          error={formError}
          onCancel={() => setDialog(null)}
          onSubmit={(input) => {
            setFormError(null);
            if (dialog.kind === "edit") {
              updateMut.mutate({ id: dialog.customer.id, input });
            } else {
              createMut.mutate(input);
            }
          }}
        />
      )}

      {dialog?.kind === "view" && (
        <CustomerDrawer
          customer={dialog.customer}
          onClose={() => setDialog(null)}
          onEdit={() => openEdit(dialog.customer)}
        />
      )}

      {dialog?.kind === "delete" && (
        <ConfirmDialog
          title="Delete customer"
          message={`Delete “${dialog.customer.name}”? This cannot be undone.`}
          confirmLabel="Delete"
          busy={deleteMut.isPending}
          error={formError}
          onCancel={() => setDialog(null)}
          onConfirm={() => deleteMut.mutate(dialog.customer.id)}
        />
      )}
    </div>
  );
}

