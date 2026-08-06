"use client";

import { useState } from "react";

import Drawer from "@/components/ui/Drawer";
import { useI18n } from "@/lib/i18n";
import type { BatchInput } from "@/lib/inventory";

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
          <input className={FIELD} value={itemCode} onChange={(e) => setItemCode(e.target.value)} required placeholder="THERMO-001" />
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
