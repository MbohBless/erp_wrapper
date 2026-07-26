"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import DocFormShell, { DOC_FIELD, DOC_GRID, DOC_LABEL } from "@/components/ui/DocFormShell";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import {
  type MaintenanceStatus,
  type Ticket,
  type TicketInput,
  createTicket,
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
            <input
              className={DOC_FIELD}
              value={form.customer}
              onChange={(e) => set("customer", e.target.value)}
              required
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("maintenance.field.equipment")}</label>
            <input
              className={DOC_FIELD}
              value={form.equipment ?? ""}
              onChange={(e) => set("equipment", e.target.value)}
              placeholder="VENT-0001"
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("maintenance.field.engineer")}</label>
            <input
              className={DOC_FIELD}
              value={form.engineer ?? ""}
              onChange={(e) => set("engineer", e.target.value)}
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
