"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import Combobox, { type ComboOption } from "@/components/ui/Combobox";
import DocFormShell, { DOC_FIELD, DOC_GRID, DOC_LABEL } from "@/components/ui/DocFormShell";
import { useAuth } from "@/lib/auth";
import { listCustomers } from "@/lib/customers";
import { listEquipment } from "@/lib/equipment";
import { useI18n } from "@/lib/i18n";
import {
  type MaintenanceStatus,
  type Ticket,
  type TicketInput,
  createTicket,
  listTickets,
  updateTicket,
} from "@/lib/maintenance";

const STATUSES: MaintenanceStatus[] = [
  "Open",
  "Scheduled",
  "In Progress",
  "Completed",
  "Cancelled",
];

export default function MaintenanceForm({ initial }: { initial?: Ticket | null }) {
  const { token } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const qc = useQueryClient();
  const editing = !!initial;

  const statusLabel: Record<MaintenanceStatus, string> = {
    Open: t("maintenance.status.open"),
    Scheduled: t("maintenance.status.scheduled"),
    "In Progress": t("maintenance.status.inProgress"),
    Completed: t("maintenance.status.completed"),
    Cancelled: t("maintenance.status.cancelled"),
  };

  // Suggestions for the reference fields. `retry: false` and the ?? [] fallback
  // are load-bearing: a Biomedical Engineer may create a ticket but may NOT read
  // /customers, so that request answers 403 for them. The field must keep
  // working as free text rather than showing an error for a list that is only
  // ever an aid.
  const suggest = { enabled: !!token, retry: false, staleTime: 60_000 };
  const customers = useQuery({
    queryKey: ["combo", "customers"],
    queryFn: () => listCustomers(token as string),
    ...suggest,
  });
  const equipment = useQuery({
    queryKey: ["combo", "equipment"],
    queryFn: () => listEquipment(token as string),
    ...suggest,
  });
  const tickets = useQuery({
    queryKey: ["combo", "tickets"],
    queryFn: () => listTickets(token as string),
    ...suggest,
  });

  const [tab, setTab] = useState("details");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<TicketInput>({
    customer: initial?.customer ?? "",
    equipment: initial?.equipment ?? "",
    engineer: initial?.engineer ?? "",
    visit_date: initial?.visit_date ?? "",
    status: initial?.status ?? "Open",
    description: initial?.description ?? "",
    parts_used: initial?.parts_used ?? "",
  });

  const set = <K extends keyof TicketInput>(k: K, v: TicketInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const customerOptions: ComboOption[] = useMemo(
    () =>
      (customers.data ?? []).map((c) => ({
        value: c.id,
        hint: c.contact_person || c.phone || null,
      })),
    [customers.data]
  );

  // Narrow the serials to the chosen customer once there is one — an engineer
  // servicing a hospital should not have to scroll past every other site's
  // equipment. Falls back to the full list when the customer is free-typed and
  // matches nothing.
  const equipmentOptions: ComboOption[] = useMemo(() => {
    const all = equipment.data ?? [];
    const mine = form.customer
      ? all.filter((e) => e.customer === form.customer)
      : [];
    return (mine.length ? mine : all).map((e) => ({
      value: e.id,
      hint: e.item_name || e.item_code || null,
    }));
  }, [equipment.data, form.customer]);

  // Engineers are free text on the ticket, so the roster is whoever has already
  // been named on one. No extra endpoint, and no dependency on /users — which
  // is Administrator-only and would leave this empty for everyone else.
  const engineerOptions: ComboOption[] = useMemo(() => {
    const seen = new Set<string>();
    for (const tk of tickets.data ?? []) {
      const name = (tk.engineer ?? "").trim();
      if (name) seen.add(name);
    }
    return [...seen].sort().map((value) => ({ value }));
  }, [tickets.data]);

  const save = useMutation({
    mutationFn: () => {
      const input: TicketInput = {
        ...form,
        equipment: form.equipment || null,
        engineer: form.engineer || null,
        visit_date: form.visit_date || null,
        description: form.description || null,
        parts_used: form.parts_used || null,
      };
      return editing
        ? updateTicket(token as string, initial!.id, input)
        : createTicket(token as string, input);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["maintenance"] });
      router.push("/maintenance");
    },
    onError: (e) => setError(e instanceof Error ? e.message : t("maintenance.err.saveFailed")),
  });

  function onSave() {
    setError(null);
    if (!form.customer.trim()) {
      setError(t("maintenance.err.customerRequired"));
      setTab("details");
      return;
    }
    save.mutate();
  }

  return (
    <DocFormShell
      breadcrumb={t("maintenance.title")}
      title={editing ? (initial!.id ?? t("maintenance.ticketFallback")) : t("maintenance.newTicketTitle")}
      statusLabel={editing ? t("common.editing") : t("common.notSaved")}
      statusTone={editing ? "muted" : "warn"}
      backHref="/maintenance"
      tabs={[
        { id: "details", label: t("common.details") },
        { id: "notes", label: t("maintenance.tab.notes") },
      ]}
      active={tab}
      onTab={setTab}
      onSave={onSave}
      saving={save.isPending}
      saveLabel={editing ? t("action.saveChanges") : t("action.create")}
      error={error}
    >
      {tab === "details" && (
        <div className={DOC_GRID}>
          <div>
            <label className={DOC_LABEL}>{t("maintenance.field.customer")} *</label>
            <Combobox
              value={form.customer}
              onChange={(v) => set("customer", v)}
              options={customerOptions}
              required
              emptyHint={t("combo.freeText")}
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("maintenance.field.equipment")}</label>
            <Combobox
              value={form.equipment ?? ""}
              onChange={(v) => set("equipment", v)}
              options={equipmentOptions}
              placeholder="VENT-0001"
              emptyHint={t("combo.freeText")}
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("maintenance.field.engineer")}</label>
            <Combobox
              value={form.engineer ?? ""}
              onChange={(v) => set("engineer", v)}
              options={engineerOptions}
              emptyHint={t("combo.freeText")}
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("maintenance.field.visitDate")}</label>
            <input
              className={DOC_FIELD}
              type="date"
              value={form.visit_date ?? ""}
              onChange={(e) => set("visit_date", e.target.value)}
            />
          </div>
          <div className="md:col-span-2">
            <label className={DOC_LABEL}>{t("common.status")}</label>
            <select
              className={DOC_FIELD}
              value={form.status}
              onChange={(e) => set("status", e.target.value as MaintenanceStatus)}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {statusLabel[s]}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {tab === "notes" && (
        <div className={DOC_GRID}>
          <div className="md:col-span-2">
            <label className={DOC_LABEL}>{t("maintenance.field.description")}</label>
            <textarea
              className={`${DOC_FIELD} min-h-[120px] resize-y`}
              value={form.description ?? ""}
              onChange={(e) => set("description", e.target.value)}
            />
          </div>
          <div className="md:col-span-2">
            <label className={DOC_LABEL}>{t("maintenance.field.parts")}</label>
            <textarea
              className={`${DOC_FIELD} min-h-[100px] resize-y`}
              value={form.parts_used ?? ""}
              onChange={(e) => set("parts_used", e.target.value)}
            />
          </div>
        </div>
      )}
    </DocFormShell>
  );
}
