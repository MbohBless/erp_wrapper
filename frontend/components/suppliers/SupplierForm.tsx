"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import DocFormShell, { DOC_FIELD, DOC_GRID, DOC_LABEL } from "@/components/ui/DocFormShell";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import {
  type Supplier,
  type SupplierInput,
  type SupplierType,
  createSupplier,
  updateSupplier,
} from "@/lib/suppliers";

export default function SupplierForm({ initial }: { initial?: Supplier | null }) {
  const editing = !!initial;
  const { token } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const qc = useQueryClient();

  const [tab, setTab] = useState("details");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: initial?.name ?? "",
    supplier_type: (initial?.supplier_type ?? "Company") as SupplierType,
    supplier_group: initial?.supplier_group ?? "All Supplier Groups",
    contact_person: initial?.contact_person ?? "",
    phone: initial?.phone ?? "",
    email: initial?.email ?? "",
    address: initial?.address ?? "",
    lead_time_days: initial?.lead_time_days?.toString() ?? "",
    tax_id: initial?.tax_id ?? "",
    disabled: initial?.disabled ?? false,
  });
  const set = (k: string, v: unknown) => setForm((f) => ({ ...f, [k]: v }));

  const save = useMutation({
    mutationFn: () => {
      const lt = parseInt(form.lead_time_days, 10);
      const input: SupplierInput = {
        name: form.name,
        supplier_type: form.supplier_type,
        supplier_group: form.supplier_group || undefined,
        contact_person: form.contact_person || null,
        phone: form.phone || null,
        email: form.email || null,
        address: form.address || null,
        lead_time_days: Number.isNaN(lt) ? null : lt,
        tax_id: form.tax_id || null,
        disabled: form.disabled,
      };
      return editing
        ? updateSupplier(token as string, initial!.id, input)
        : createSupplier(token as string, input);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["suppliers"] });
      router.push("/suppliers");
    },
    onError: (e) => setError(e instanceof Error ? e.message : t("suppliers.error.save")),
  });

  function onSave() {
    setError(null);
    if (!form.name.trim()) {
      setError(t("suppliers.error.nameRequired"));
      setTab("details");
      return;
    }
    save.mutate();
  }

  return (
    <DocFormShell
      breadcrumb={t("suppliers.title")}
      title={editing ? initial!.name : t("suppliers.newTitle")}
      statusLabel={editing ? t("common.editing") : t("common.notSaved")}
      statusTone={editing ? "muted" : "warn"}
      backHref="/suppliers"
      tabs={[
        { id: "details", label: t("common.details") },
        { id: "more", label: t("common.moreInfo") },
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
          <div className="md:col-span-2">
            <label className={DOC_LABEL}>{t("suppliers.field.supplierName")} *</label>
            <input
              className={DOC_FIELD}
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              required
              disabled={editing}
              placeholder={t("suppliers.namePlaceholder")}
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("suppliers.field.type")}</label>
            <select className={DOC_FIELD} value={form.supplier_type} onChange={(e) => set("supplier_type", e.target.value)}>
              <option value="Company">{t("suppliers.type.company")}</option>
              <option value="Individual">{t("suppliers.type.individual")}</option>
            </select>
          </div>
          <div>
            <label className={DOC_LABEL}>{t("suppliers.field.phone")}</label>
            <input className={DOC_FIELD} value={form.phone} onChange={(e) => set("phone", e.target.value)} />
          </div>
          <div className="md:col-span-2">
            <label className={DOC_LABEL}>{t("suppliers.field.email")}</label>
            <input className={DOC_FIELD} type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
          </div>

          <div className="md:col-span-2">
            <label className={DOC_LABEL}>{t("suppliers.field.address")}</label>
            <textarea className={`${DOC_FIELD} min-h-[80px] resize-y`} value={form.address} onChange={(e) => set("address", e.target.value)} />
          </div>
        </div>
      )}

      {tab === "more" && (
        <div className={DOC_GRID}>
          <div>
            <label className={DOC_LABEL}>{t("suppliers.field.supplierGroup")}</label>
            <input className={DOC_FIELD} value={form.supplier_group} onChange={(e) => set("supplier_group", e.target.value)} />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("suppliers.field.leadTime")}</label>
            <input className={DOC_FIELD} type="number" min="0" value={form.lead_time_days} onChange={(e) => set("lead_time_days", e.target.value)} />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("suppliers.field.contactPerson")}</label>
            <input className={DOC_FIELD} value={form.contact_person} onChange={(e) => set("contact_person", e.target.value)} />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("suppliers.field.taxId")}</label>
            <input className={DOC_FIELD} value={form.tax_id} onChange={(e) => set("tax_id", e.target.value)} />
          </div>
          <label className="md:col-span-2 flex items-center gap-2.5 text-sm cursor-pointer">
            <input type="checkbox" checked={form.disabled} onChange={(e) => set("disabled", e.target.checked)} />
            {t("suppliers.disabledHint")}
          </label>
        </div>
      )}
    </DocFormShell>
  );
}
