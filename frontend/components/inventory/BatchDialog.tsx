"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import Combobox, { type ComboOption } from "@/components/ui/Combobox";
import Drawer from "@/components/ui/Drawer";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { BatchInput } from "@/lib/inventory";
import { listProducts } from "@/lib/products";

const FIELD = "eq-field w-full px-3 py-2.5 text-sm";
const LABEL = "block text-[13px] muted mb-1.5";
const FORM_ID = "batch-form";

export default function BatchDialog({
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  busy: boolean;
  error: string | null;
  onSubmit: (input: BatchInput) => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const { token } = useAuth();

  // Only batch-tracked products can carry a batch — ERPNext rejects the rest
  // with "The selected item cannot have Batch". Offering the full catalogue
  // would suggest choices that are guaranteed to fail on save.
  const products = useQuery({
    queryKey: ["combo", "products", "batch-tracked"],
    queryFn: () => listProducts(token as string),
    enabled: !!token,
    retry: false,
    staleTime: 60_000,
  });
  const skuOptions: ComboOption[] = useMemo(
    () =>
      (products.data ?? [])
        .filter((p) => p.track_batches)
        .map((p) => ({ value: p.sku, hint: p.name })),
    [products.data]
  );
  const trackedCount = skuOptions.length;

  const [batchId, setBatchId] = useState("");
  const [itemCode, setItemCode] = useState("");
  const [expiry, setExpiry] = useState("");
  const [mfg, setMfg] = useState("");

  return (
    <Drawer
      eyebrow={t("inventory.title")}
      title={t("inventory.newBatch")}
      onClose={onCancel}
      footer={
        <>
          <button type="button" onClick={onCancel} className="btn btn-text">
            {t("action.cancel")}
          </button>
          <button type="submit" form={FORM_ID} disabled={busy} className="btn btn-filled">
            {busy ? t("action.saving") : t("inventory.createBatch")}
          </button>
        </>
      }
    >
      {error && (
        <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px] mb-4">
          {error}
        </div>
      )}
      <form
        id={FORM_ID}
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({
            batch_id: batchId,
            item_code: itemCode,
            expiry_date: expiry || null,
            manufacturing_date: mfg || null,
          });
        }}
      >
        <div>
          <label className={LABEL}>{t("inventory.batchNumber")} *</label>
          <input className={FIELD} value={batchId} onChange={(e) => setBatchId(e.target.value)} required placeholder="BATCH-001" />
        </div>
        <div>
          <label className={LABEL}>{t("inventory.batchProduct")} *</label>
          <Combobox
            value={itemCode}
            onChange={setItemCode}
            options={skuOptions}
            required
            placeholder="THERMO-001"
            emptyHint={
              trackedCount === 0
                ? t("inventory.noBatchTrackedProducts")
                : t("combo.freeText")
            }
          />
        </div>
        <div>
          <label className={LABEL}>{t("inventory.expiryDate")}</label>
          <input className={FIELD} type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
        </div>
        <div>
          <label className={LABEL}>{t("inventory.manufacturingDate")}</label>
          <input className={FIELD} type="date" value={mfg} onChange={(e) => setMfg(e.target.value)} />
        </div>
      </form>
    </Drawer>
  );
}
