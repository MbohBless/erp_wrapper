"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import DocFormShell, {
  DOC_FIELD,
  DOC_GRID,
  DOC_LABEL,
} from "@/components/ui/DocFormShell";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import {
  type Equipment,
  type EquipmentInput,
  type EquipmentStatus,
  createEquipment,
  updateEquipment,
} from "@/lib/equipment";

const STATUSES: EquipmentStatus[] = [
  "In Store",
  "Installed",
  "Under Repair",
  "Decommissioned",
];

export default function EquipmentForm({ initial }: { initial?: Equipment | null }) {
  const editing = !!initial;
  const { token } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const qc = useQueryClient();

  const statusLabel: Record<EquipmentStatus, string> = {
    "In Store": t("equipment.status.inStore"),
    Installed: t("equipment.status.installed"),
    "Under Repair": t("equipment.status.underRepair"),
    Decommissioned: t("equipment.status.decommissioned"),
  };

  const [tab, setTab] = useState("details");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<EquipmentInput>({
    serial_no: initial?.serial_no ?? "",
    item_code: initial?.item_code ?? "",
    customer: initial?.customer ?? "",
    installation_date: initial?.installation_date ?? "",
    warranty_expiry_date: initial?.warranty_expiry_date ?? "",
    status: initial?.status ?? "In Store",
  });

  const set = <K extends keyof EquipmentInput>(k: K, v: EquipmentInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const save = useMutation({
    mutationFn: () => {
      const input: EquipmentInput = {
        ...form,
        customer: form.customer || null,
        installation_date: form.installation_date || null,
        warranty_expiry_date: form.warranty_expiry_date || null,
      };
      return editing
        ? updateEquipment(token as string, initial!.id, input)
        : createEquipment(token as string, input);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["equipment"] });
      router.push("/equipment");
    },
    onError: (e) => setError(e instanceof Error ? e.message : t("equipment.err.saveFailed")),
  });

  function onSave() {
    setError(null);
    if (!form.serial_no.trim()) {
      setError(t("equipment.err.serialRequired"));
      setTab("details");
      return;
    }
    if (!form.item_code.trim()) {
      setError(t("equipment.err.skuRequired"));
      setTab("details");
      return;
    }
    save.mutate();
  }

  return (
    <DocFormShell
      breadcrumb={t("equipment.title")}
      title={editing ? initial!.serial_no : t("equipment.registerTitle")}
      statusLabel={editing ? t("common.editing") : t("common.notSaved")}
      statusTone={editing ? "muted" : "warn"}
      backHref="/equipment"
      tabs={[
        { id: "details", label: t("common.details") },
        { id: "lifecycle", label: t("equipment.tab.lifecycle") },
      ]}
      active={tab}
      onTab={setTab}
      onSave={onSave}
      saving={save.isPending}
      saveLabel={editing ? t("action.saveChanges") : t("equipment.registerShort")}
      error={error}
    >
      {tab === "details" && (
        <div className={DOC_GRID}>
          <div>
            <label className={DOC_LABEL}>{t("equipment.field.serial")} *</label>
            <input
              className={DOC_FIELD}
              value={form.serial_no}
              onChange={(e) => set("serial_no", e.target.value)}
              required
              disabled={editing}
              placeholder="VENT-0001"
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("equipment.field.sku")} *</label>
            <input
              className={DOC_FIELD}
              value={form.item_code}
              onChange={(e) => set("item_code", e.target.value)}
              required
              placeholder="VENTILATOR-X"
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("equipment.field.customer")}</label>
            <input
              className={DOC_FIELD}
              value={form.customer ?? ""}
              onChange={(e) => set("customer", e.target.value)}
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("common.status")}</label>
            <select
              className={DOC_FIELD}
              value={form.status}
              onChange={(e) => set("status", e.target.value as EquipmentStatus)}
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

      {tab === "lifecycle" && (
        <div className={DOC_GRID}>
          <div>
            <label className={DOC_LABEL}>{t("equipment.field.installDate")}</label>
            <input
              className={DOC_FIELD}
              type="date"
              value={form.installation_date ?? ""}
              onChange={(e) => set("installation_date", e.target.value)}
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("equipment.field.warranty")}</label>
            <input
              className={DOC_FIELD}
              type="date"
              value={form.warranty_expiry_date ?? ""}
              onChange={(e) => set("warranty_expiry_date", e.target.value)}
            />
          </div>
        </div>
      )}
    </DocFormShell>
  );
}
