"use client";

import type { ReactNode } from "react";
import { useRouter } from "next/navigation";

import { Icon } from "@/components/icons";

export type DocTab = { id: string; label: string };

const TONE: Record<string, string> = {
  warn: "bg-[color-mix(in_srgb,var(--warn-raw)_16%,transparent)] text-warn",
  ok: "bg-[color-mix(in_srgb,var(--ok-raw)_16%,transparent)] text-ok",
  muted: "bg-[color-mix(in_srgb,var(--color-text)_10%,transparent)] muted",
};

/**
 * ERPNext-style full-page document form chrome: header (back, breadcrumb, title,
 * status pill, Cancel/Save) plus a tab strip. Callers render the active tab's
 * fields as children. Keeps every create/edit form visually identical.
 */
export default function DocFormShell({
  breadcrumb,
  title,
  statusLabel,
  statusTone = "warn",
  backHref,
  tabs,
  active,
  onTab,
  onSave,
  saving,
  saveLabel = "Save",
  error,
  children,
}: {
  breadcrumb: string;
  title: string;
  statusLabel?: string;
  statusTone?: "warn" | "ok" | "muted";
  backHref: string;
  tabs: DocTab[];
  active: string;
  onTab: (id: string) => void;
  onSave: () => void;
  saving: boolean;
  saveLabel?: string;
  error?: string | null;
  children: ReactNode;
}) {
  const router = useRouter();

  return (
    <div className="eq-view -mt-1">
      <div className="flex items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={() => router.push(backHref)}
            className="icobtn grid place-items-center w-9 h-9 border border-divider muted rotate-90"
            title="Back"
          >
            <Icon name="chevronDown" size={18} />
          </button>
          <div className="min-w-0">
            <nav className="flex items-center gap-2 text-xs muted">
              <span>{breadcrumb}</span>
              <span>›</span>
              <span className="text-ink truncate">{title}</span>
            </nav>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-heading font-semibold truncate">{title}</h1>
              {statusLabel && (
                <span className={`text-[11px] px-2 py-0.5 rounded-full shrink-0 ${TONE[statusTone]}`}>
                  {statusLabel}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <button type="button" onClick={() => router.push(backHref)} className="btn btn-text">
            Cancel
          </button>
          <button type="button" onClick={onSave} disabled={saving} className="btn btn-filled">
            {saving ? "Saving…" : saveLabel}
          </button>
        </div>
      </div>

      <div className="blueprint bg-bg p-0 overflow-hidden">
        <div className="flex items-center gap-1 border-b border-divider px-4 overflow-x-auto eq-scroll">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => onTab(t.id)}
              className={`relative px-4 py-3 text-sm font-heading font-semibold -mb-px whitespace-nowrap ${
                active === t.id ? "text-ink" : "muted hover:text-ink"
              }`}
            >
              {t.label}
              {active === t.id && (
                <span className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />
              )}
            </button>
          ))}
        </div>

        {error && (
          <div className="mx-6 mt-5 text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px]">
            {error}
          </div>
        )}

        {children}
      </div>
    </div>
  );
}

/** Shared field classes for full-page document forms. */
export const DOC_FIELD = "eq-field w-full px-3 py-2.5 text-sm";
export const DOC_LABEL = "block text-[13px] muted mb-1.5";
/** Two/three-column grid used inside a tab panel. */
export const DOC_GRID = "p-6 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5";
export const DOC_GRID3 = "p-6 grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-5";
