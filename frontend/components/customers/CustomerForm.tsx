"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import DocFormShell, { DOC_FIELD, DOC_GRID, DOC_LABEL } from "@/components/ui/DocFormShell";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useReferenceOptions } from "@/lib/reference";
import {
  type Customer,
  type CustomerInput,
  type CustomerType,
  createCustomer,
  updateCustomer,
} from "@/lib/customers";

export default function CustomerForm({ initial }: { initial?: Customer | null }) {
  const editing = !!initial;
  const { token } = useAuth();
  const { t } = useI18n();
  const { options } = useReferenceOptions();
  const router = useRouter();
  const qc = useQueryClient();

  const [tab, setTab] = useState("details");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<CustomerInput>({
    name: initial?.name ?? "",
    customer_type: initial?.customer_type ?? "Company",
    // Empty, not the tree roots: those are exactly the values ERPNext refuses.
    // The server fills a sensible group when this is left blank.
    customer_group: initial?.customer_group ?? "",
    territory: initial?.territory ?? "",
    contact_person: initial?.contact_person ?? "",
    phone: initial?.phone ?? "",
    email: initial?.email ?? "",
    address: initial?.address ?? "",
    tax_id: initial?.tax_id ?? "",
    disabled: initial?.disabled ?? false,
  });

  const set = <K extends keyof CustomerInput>(k: K, v: CustomerInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const save = useMutation({
    mutationFn: () => {
      const input: CustomerInput = {
        ...form,
        contact_person: form.contact_person || null,
        phone: form.phone || null,
        email: form.email || null,
        address: form.address || null,
        tax_id: form.tax_id || null,
      };
      return editing
        ? updateCustomer(token as string, initial!.id, input)
        : createCustomer(token as string, input);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customers"] });
      router.push("/customers");
    },
    onError: (e) => setError(e instanceof Error ? e.message : t("customers.error.save")),
  });

  function onSave() {
    setError(null);
    if (!form.name.trim()) {
      setError(t("customers.error.nameRequired"));
      setTab("details");
      return;
    }
    // Required, even though the server can substitute one. The revenue-by-
    // segment chart is built from this field, so a guessed group files the
    // customer under the wrong segment and quietly skews the reporting.
    if (!form.customer_group) {
      setError(t("customers.error.groupRequired"));
      setTab("details");
      return;
    }
    save.mutate();
  }

  return (
    <DocFormShell
      breadcrumb={t("customers.title")}
      title={editing ? initial!.name : t("customers.newTitle")}
      statusLabel={editing ? t("common.editing") : t("common.notSaved")}
      statusTone={editing ? "muted" : "warn"}
      backHref="/customers"
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
            <label className={DOC_LABEL}>{t("customers.field.accountName")} *</label>
            <input
              className={DOC_FIELD}
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              required
              disabled={editing}
              placeholder={t("customers.namePlaceholder")}
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("customers.field.customerGroup")} *</label>
            {/* On the first tab because this is the field every user sets, and
                the revenue-by-segment chart is built from it. A select, not free
                text: ERPNext accepts only these, and the old default was a tree
                root it refuses outright — which broke every create. */}
            <select
              className={DOC_FIELD}
              value={form.customer_group ?? ""}
              onChange={(e) => set("customer_group", e.target.value)}
              required
            >
              <option value="">{t("common.choose")}</option>
              {(options?.customer_groups ?? []).map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={DOC_LABEL}>{t("customers.field.phone")}</label>
            <input
              className={DOC_FIELD}
              value={form.phone ?? ""}
              onChange={(e) => set("phone", e.target.value)}
            />
          </div>
          <div className="md:col-span-2">
            <label className={DOC_LABEL}>{t("customers.field.email")}</label>
            <input
              className={DOC_FIELD}
              type="email"
              value={form.email ?? ""}
              onChange={(e) => set("email", e.target.value)}
            />
          </div>
        </div>
      )}

      {tab === "more" && (
        <div className={DOC_GRID}>
          <div>
            <label className={DOC_LABEL}>{t("customers.field.type")}</label>
            <select
              className={DOC_FIELD}
              value={form.customer_type}
              onChange={(e) => set("customer_type", e.target.value as CustomerType)}
            >
              <option value="Company">{t("customers.type.company")}</option>
              <option value="Individual">{t("customers.type.individual")}</option>
            </select>
            <div className="text-[12px] muted mt-1">
              {t("customers.type.hint")}
            </div>
          </div>
          <div>
            <label className={DOC_LABEL}>{t("customers.field.territory")}</label>
            <select
              className={DOC_FIELD}
              value={form.territory ?? ""}
              onChange={(e) => set("territory", e.target.value)}
            >
              <option value="">{t("common.choose")}</option>
              {(options?.territories ?? []).map((tr) => (
                <option key={tr} value={tr}>{tr}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={DOC_LABEL}>{t("customers.field.contactPerson")}</label>
            <input
              className={DOC_FIELD}
              value={form.contact_person ?? ""}
              onChange={(e) => set("contact_person", e.target.value)}
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("customers.field.taxId")}</label>
            <input
              className={DOC_FIELD}
              value={form.tax_id ?? ""}
              onChange={(e) => set("tax_id", e.target.value)}
            />
          </div>
          <div className="md:col-span-2">
            <label className={DOC_LABEL}>{t("customers.field.address")}</label>
            <textarea
              className={`${DOC_FIELD} min-h-[80px] resize-y`}
              value={form.address ?? ""}
              onChange={(e) => set("address", e.target.value)}
            />
          </div>
          <label className="md:col-span-2 flex items-center gap-2.5 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={!!form.disabled}
              onChange={(e) => set("disabled", e.target.checked)}
            />
            {t("customers.disabledHint")}
          </label>
        </div>
      )}
    </DocFormShell>
  );
}
