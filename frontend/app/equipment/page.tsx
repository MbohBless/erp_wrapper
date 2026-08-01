"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import AppShell from "@/components/AppShell";
import Blueprint from "@/components/Blueprint";
import ConfirmDialog from "@/components/ConfirmDialog";
import EquipmentDrawer from "@/components/equipment/EquipmentDrawer";
import { Icon } from "@/components/icons";
import RowActions from "@/components/ui/RowActions";
import StatusTag, { type Tone } from "@/components/ui/StatusTag";
import TableSkeleton from "@/components/ui/TableSkeleton";
import { useDebounced } from "@/components/ui/hooks";
import { UnauthorizedError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useAppName } from "@/lib/branding";
import {
  type Equipment,
  deleteEquipment,
  installEquipment,
  listEquipment,
} from "@/lib/equipment";

const STATUS_TONE: Record<string, Tone> = {
  Installed: "ok",
  "In Store": "accent",
  "Under Repair": "warn",
  Decommissioned: "neutral",
};

export default function EquipmentPage() {
  return (
    <AppShell>
      <EquipmentContent />
    </AppShell>
  );
}


type Dialog =
  | { kind: "view"; eq: Equipment }
  | { kind: "delete"; eq: Equipment }
  | null;

function EquipmentContent() {
  const appName = useAppName();
  const { token, logout } = useAuth();
  const { t } = useI18n();
  const router = useRouter();
  const qc = useQueryClient();
  const [searchInput, setSearchInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dialog, setDialog] = useState<Dialog>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const search = useDebounced(searchInput);

  const { data, isLoading, error } = useQuery({
    queryKey: ["equipment", search, statusFilter],
    queryFn: () =>
      listEquipment(token as string, {
        search: search || undefined,
        status: statusFilter || undefined,
      }),
    enabled: !!token,
  });

  useEffect(() => {
    if (error instanceof UnauthorizedError) logout();
  }, [error, logout]);

  const rows = useMemo(() => data ?? [], [data]);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["equipment"] });

  const editHref = (eq: Equipment) => `/equipment/${encodeURIComponent(eq.id)}/edit`;

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteEquipment(token as string, id),
    onSuccess: () => { invalidate(); setDialog(null); },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });
  const installMut = useMutation({
    mutationFn: (id: string) => installEquipment(token as string, id),
    onSuccess: (updated) => {
      invalidate();
      setDialog({ kind: "view", eq: updated });
    },
    onError: (e) => setFormError(e instanceof Error ? e.message : "Failed"),
  });

  return (
    <div className="eq-view">
      <nav className="flex items-center gap-2 text-xs muted mb-3">
        <span>{appName}</span>
        <span>›</span>
        <span className="text-ink">{t("equipment.title")}</span>
      </nav>
      <div className="flex items-end justify-between gap-5 flex-wrap mb-5">
        <div>
          <h1 className="text-[32px] mb-1">{t("equipment.title")}</h1>
          <p className="muted text-sm m-0">{t("equipment.subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => router.push("/equipment/new")}
          className="btn btn-filled"
        >
          <Icon name="plus" size={15} sw={1.8} />
          {t("equipment.register")}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 mb-4">
        <div className="relative w-full sm:w-[340px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 muted-3">
            <Icon name="search" size={15} />
          </span>
          <input
            className="eq-field w-full h-[38px] pl-8 pr-3 text-sm"
            placeholder={t("equipment.searchPlaceholder")}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <select
          className="eq-field h-[38px] px-3 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">{t("equipment.allStatuses")}</option>
          <option value="In Store">{t("equipment.status.inStore")}</option>
          <option value="Installed">{t("equipment.status.installed")}</option>
          <option value="Under Repair">{t("equipment.status.underRepair")}</option>
          <option value="Decommissioned">{t("equipment.status.decommissioned")}</option>
        </select>
      </div>

      <Blueprint className="p-0 overflow-hidden">
        <div className="overflow-x-auto eq-scroll">
          <table className="w-full text-sm border-collapse min-w-[880px]">
            <thead>
              <tr className="muted">
                {[t("equipment.col.serial"), t("equipment.col.product"), t("equipment.col.customer"), t("equipment.col.installed"), t("equipment.col.warranty"), t("common.status"), ""].map(
                  (h, i) => (
                    <th key={i} className={`text-[11px] tracking-[0.08em] uppercase font-semibold py-3 border-b border-divider ${i === 0 ? "text-left pl-5" : "text-left"}`}>
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
                <tr><td colSpan={7} className="py-10 text-center muted">{t("equipment.loadError")}</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={7} className="py-12 text-center muted-2">{t("equipment.empty")}</td></tr>
              ) : (
                rows.map((eq) => (
                  <tr key={eq.id} className="group border-b border-solid divide-soft hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
                    <td className="pl-5 py-3 font-heading tracking-wide">{eq.serial_no}</td>
                    <td className="py-3 font-medium">{eq.item_name || eq.item_code}</td>
                    <td className="py-3 muted">{eq.customer ?? "—"}</td>
                    <td className="py-3 muted">{eq.installation_date ?? "—"}</td>
                    <td className="py-3 muted">{eq.warranty_expiry_date ?? "—"}</td>
                    <td className="py-3">
                      <StatusTag label={eq.status} tone={STATUS_TONE[eq.status] ?? "neutral"} />
                    </td>
                    <td className="py-3 pr-4">
                      <RowActions
                        onView={() => setDialog({ kind: "view", eq })}
                        onEdit={() => router.push(editHref(eq))}
                        onDelete={() => { setFormError(null); setDialog({ kind: "delete", eq }); }}
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Blueprint>

      {dialog?.kind === "view" && (
        <EquipmentDrawer
          equipment={dialog.eq}
          installing={installMut.isPending}
          onClose={() => setDialog(null)}
          onEdit={() => router.push(editHref(dialog.eq))}
          onInstall={() => installMut.mutate(dialog.eq.id)}
        />
      )}
      {dialog?.kind === "delete" && (
        <ConfirmDialog
          title={t("equipment.deleteTitle")}
          message={`${t("equipment.deletePrompt")} “${dialog.eq.serial_no}” ? ${t("common.deleteConfirm")}`}
          confirmLabel={t("action.delete")}
          busy={deleteMut.isPending}
          error={formError}
          onCancel={() => setDialog(null)}
          onConfirm={() => deleteMut.mutate(dialog.eq.id)}
        />
      )}
    </div>
  );
}
