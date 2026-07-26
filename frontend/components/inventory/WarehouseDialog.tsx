"use client";

import { useState } from "react";

import Drawer from "@/components/ui/Drawer";
import { useI18n } from "@/lib/i18n";
import type { Warehouse, WarehouseInput } from "@/lib/inventory";

const FIELD = "eq-field w-full px-3 py-2.5 text-sm";
const LABEL = "block text-[13px] muted mb-1.5";
const FORM_ID = "warehouse-form";

export default function WarehouseDialog({
  initial,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: Warehouse | null;
  busy: boolean;
  error: string | null;
  onSubmit: (input: WarehouseInput) => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const editing = !!initial;
  const [name, setName] = useState(initial?.name ?? "");
  const [parent, setParent] = useState(initial?.parent_warehouse ?? "");
  const [isGroup, setIsGroup] = useState(initial?.is_group ?? false);
  const [disabled, setDisabled] = useState(initial?.disabled ?? false);

  return (
    <Drawer
      eyebrow={t("inventory.title")}
      title={editing ? t("inventory.editWarehouse") : t("inventory.newWarehouse")}
      onClose={onCancel}
      footer={
        <>
          <button type="button" onClick={onCancel} className="btn btn-text">
            {t("action.cancel")}
          </button>
          <button type="submit" form={FORM_ID} disabled={busy} className="btn btn-filled">
            {busy ? t("action.saving") : editing ? t("action.saveChanges") : t("inventory.createWarehouse")}
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
            name,
            parent_warehouse: parent || null,
            is_group: isGroup,
            disabled,
          });
        }}
      >
        <div>
          <label className={LABEL}>{t("inventory.warehouseName")} *</label>
          <input
            className={FIELD}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            disabled={editing}
            placeholder={t("inventory.warehouseNamePlaceholder")}
          />
        </div>
        <div>
          <label className={LABEL}>{t("inventory.parentWarehouse")}</label>
          <input
            className={FIELD}
            value={parent}
            onChange={(e) => setParent(e.target.value)}
            placeholder={t("inventory.optional")}
          />
        </div>
        <label className="flex items-center gap-2.5 text-sm cursor-pointer">
          <input type="checkbox" checked={isGroup} onChange={(e) => setIsGroup(e.target.checked)} />
          {t("inventory.groupWarehouse")}
        </label>
        <label className="flex items-center gap-2.5 text-sm cursor-pointer">
          <input type="checkbox" checked={disabled} onChange={(e) => setDisabled(e.target.checked)} />
          {t("common.disabled")}
        </label>
      </form>
    </Drawer>
  );
}
