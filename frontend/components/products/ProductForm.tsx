"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import DocFormShell, { DOC_FIELD, DOC_GRID, DOC_LABEL } from "@/components/ui/DocFormShell";
import { groupNum } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import {
  type Product,
  type ProductInput,
  createProduct,
  updateProduct,
} from "@/lib/products";

type FormState = {
  name: string;
  sku: string;
  category: string;
  unit: string;
  manufacturer: string;
  barcode: string;
  purchase_price: string;
  selling_price: string;
  image: string;
  track_batches: boolean;
  disabled: boolean;
};

const num = (s: string): number | null => {
  const n = parseFloat(s.replace(/[^\d.-]/g, ""));
  return s.trim() === "" || Number.isNaN(n) ? null : n;
};

export default function ProductForm({ initial }: { initial?: Product | null }) {
  const editing = !!initial;
  const { token } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const qc = useQueryClient();

  const [tab, setTab] = useState("details");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>({
    name: initial?.name ?? "",
    sku: initial?.sku ?? "",
    category: initial?.category ?? "All Item Groups",
    unit: initial?.unit ?? "Nos",
    manufacturer: initial?.manufacturer ?? "",
    barcode: initial?.barcode ?? "",
    purchase_price: initial?.purchase_price != null ? groupNum(String(initial.purchase_price)) : "",
    selling_price: initial?.selling_price != null ? groupNum(String(initial.selling_price)) : "",
    image: initial?.image ?? "",
    track_batches: initial?.track_batches ?? false,
    disabled: initial?.disabled ?? false,
  });
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const save = useMutation({
    mutationFn: (input: ProductInput) =>
      editing ? updateProduct(token as string, initial!.id, input) : createProduct(token as string, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["products"] });
      router.push("/products");
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed"),
  });

  function onSave() {
    setError(null);
    save.mutate({
      name: form.name,
      sku: form.sku,
      category: form.category || undefined,
      unit: form.unit || undefined,
      manufacturer: form.manufacturer || null,
      barcode: form.barcode || null,
      purchase_price: num(form.purchase_price),
      selling_price: num(form.selling_price),
      image: form.image || null,
      track_batches: form.track_batches,
      disabled: form.disabled,
    });
  }

  return (
    <DocFormShell
      breadcrumb={t("products.title")}
      title={editing ? initial!.name : t("products.newProduct")}
      statusLabel={editing ? t("common.editing") : t("common.notSaved")}
      statusTone={editing ? "muted" : "warn"}
      backHref="/products"
      tabs={[
        { id: "details", label: t("common.details") },
        { id: "pricing", label: t("products.tabPricing") },
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
            <label className={DOC_LABEL}>{t("products.name")} *</label>
            <input
              className={DOC_FIELD}
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              required
              placeholder={t("products.namePlaceholder")}
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("products.sku")} *</label>
            <input
              className={DOC_FIELD}
              value={form.sku}
              onChange={(e) => set("sku", e.target.value)}
              required
              disabled={editing}
              placeholder="THERMO-001"
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("products.category")}</label>
            <input className={DOC_FIELD} value={form.category} onChange={(e) => set("category", e.target.value)} />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("products.sellingPriceXaf")}</label>
            <input
              className={DOC_FIELD}
              inputMode="numeric"
              value={form.selling_price}
              onChange={(e) => set("selling_price", groupNum(e.target.value))}
            />
          </div>
        </div>
      )}

      {tab === "pricing" && (
        <div className={DOC_GRID}>
          <div>
            <label className={DOC_LABEL}>{t("products.unit")}</label>
            <input className={DOC_FIELD} value={form.unit} onChange={(e) => set("unit", e.target.value)} />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("products.purchasePriceXaf")}</label>
            <input
              className={DOC_FIELD}
              inputMode="numeric"
              value={form.purchase_price}
              onChange={(e) => set("purchase_price", groupNum(e.target.value))}
            />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("products.manufacturer")}</label>
            <input className={DOC_FIELD} value={form.manufacturer} onChange={(e) => set("manufacturer", e.target.value)} />
          </div>
          <div>
            <label className={DOC_LABEL}>{t("products.barcode")}</label>
            <input className={DOC_FIELD} value={form.barcode} onChange={(e) => set("barcode", e.target.value)} />
          </div>
          <div className="md:col-span-2">
            <label className={DOC_LABEL}>{t("products.imageUrl")}</label>
            <input className={DOC_FIELD} value={form.image} onChange={(e) => set("image", e.target.value)} />
          </div>
          <label className="md:col-span-2 flex items-start gap-2.5 text-sm cursor-pointer">
            <input
              type="checkbox"
              className="mt-1"
              checked={form.track_batches}
              // ERPNext will not let this be turned on once the item has stock
              // movements, so it is effectively a decision made at creation.
              disabled={editing && (initial?.track_batches ?? false)}
              onChange={(e) => set("track_batches", e.target.checked)}
            />
            <span>
              {t("products.trackBatches")}
              <span className="block text-[12px] muted">{t("products.trackBatchesHint")}</span>
            </span>
          </label>
          <label className="md:col-span-2 flex items-center gap-2.5 text-sm cursor-pointer">
            <input type="checkbox" checked={form.disabled} onChange={(e) => set("disabled", e.target.checked)} />
            {t("products.disabledHint")}
          </label>
        </div>
      )}
    </DocFormShell>
  );
}
