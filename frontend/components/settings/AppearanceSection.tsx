"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import Blueprint from "@/components/Blueprint";
import { Icon } from "@/components/icons";
import { useBranding } from "@/lib/branding";
import {
  ALL_WIDGET_IDS,
  WIDGET_LABELS,
  WIDGET_VIZ,
  type BrandingSettings,
  type DashboardWidget,
  type VizType,
  type WidgetId,
  DEFAULT_LAYOUT,
  getBrandingSettings,
  resetDashboardLayout,
  updateBrandingSettings,
  updateDashboardLayout,
} from "@/lib/dashboard";

/**
 * White-label controls: product identity, theme colours and dashboard layout.
 *
 * Colours are constrained to hex here because the API only accepts hex — the
 * form should not let someone compose a payload the server will reject. A 402
 * from the API means the tenant's plan does not include the capability, which
 * is surfaced inline rather than as a generic error.
 */

// Mirrors the :root and :root[data-theme="dark"] blocks in app/globals.css.
// Held explicitly rather than read with getComputedStyle: the dark column must
// show dark defaults while the page itself is in light mode, and the computed
// style only ever reflects the theme currently applied.
const DEFAULT_TOKENS: Record<"light_tokens" | "dark_tokens", Record<string, string>> = {
  light_tokens: {
    "--color-accent": "#5980a6",
    "--color-bg": "#f2f2f3",
    "--color-surface": "#e9e9ea",
    "--color-text": "#1d1f20",
  },
  dark_tokens: {
    "--color-accent": "#8fb4d8",
    "--color-bg": "#12171d",
    "--color-surface": "#1a2129",
    "--color-text": "#eef2f6",
  },
};

const THEME_FIELDS: { token: string; label: string }[] = [
  { token: "--color-accent", label: "Accent" },
  { token: "--color-bg", label: "Background" },
  { token: "--color-surface", label: "Surface" },
  { token: "--color-text", label: "Text" },
];

const FIELD =
  "eq-field w-full px-3 py-2.5 text-sm bg-transparent border border-divider rounded-lg";

const MAX_LOGO_BYTES = 400 * 1024;

export default function AppearanceSection({
  token,
  canEdit,
}: {
  token: string;
  canEdit: boolean;
}) {
  const qc = useQueryClient();
  const { refresh } = useBranding();
  const [form, setForm] = useState<BrandingSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["branding-settings"],
    queryFn: () => getBrandingSettings(token),
  });

  useEffect(() => {
    if (data && !form) setForm(data);
  }, [data, form]);

  const afterSave = (next: BrandingSettings) => {
    setForm(next);
    setSaved(true);
    setError(null);
    qc.setQueryData(["branding-settings"], next);
    // Re-fetch the public projection so the running app re-skins immediately.
    refresh();
    setTimeout(() => setSaved(false), 2500);
  };

  const onError = (e: unknown) =>
    setError(e instanceof Error ? e.message : "Could not save appearance");

  const saveMut = useMutation({
    mutationFn: (v: BrandingSettings) => updateBrandingSettings(token, v),
    onSuccess: afterSave,
    onError,
  });
  const layoutMut = useMutation({
    mutationFn: (widgets: DashboardWidget[]) =>
      updateDashboardLayout(token, { widgets }),
    onSuccess: afterSave,
    onError,
  });
  const resetMut = useMutation({
    mutationFn: () => resetDashboardLayout(token),
    onSuccess: afterSave,
    onError,
  });

  if (isLoading || !form) {
    return (
      <Blueprint className="p-6">
        <div className="font-heading font-semibold text-base mb-4">Appearance</div>
        <div className="h-24 animate-pulse rounded-lg bg-[color-mix(in_srgb,var(--color-text)_5%,transparent)]" />
      </Blueprint>
    );
  }

  const set = <K extends keyof BrandingSettings>(key: K, value: BrandingSettings[K]) =>
    setForm({ ...form, [key]: value });

  const setToken = (mode: "light_tokens" | "dark_tokens", name: string, value: string) =>
    setForm({ ...form, [mode]: { ...form[mode], [name]: value } });

  const widgets: DashboardWidget[] = form.dashboard?.widgets?.length
    ? form.dashboard.widgets
    : DEFAULT_LAYOUT.widgets;

  const patchWidget = (id: WidgetId, patch: Partial<DashboardWidget>) =>
    layoutMut.mutate(widgets.map((w) => (w.id === id ? { ...w, ...patch } : w)));

  const move = (index: number, delta: number) => {
    const next = [...widgets];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    layoutMut.mutate(next);
  };

  const addWidget = (id: WidgetId) => {
    const viz = WIDGET_VIZ[id]?.[0] ?? null;
    layoutMut.mutate([...widgets, { id, visible: true, span: 1, viz, title: null }]);
  };

  const missing = ALL_WIDGET_IDS.filter((id) => !widgets.some((w) => w.id === id));

  const readFile = (file: File, onDone: (dataUrl: string) => void) => {
    if (file.size > MAX_LOGO_BYTES) {
      setError("Image is too large — keep logos under 400 KB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => onDone(String(reader.result || ""));
    reader.readAsDataURL(file);
  };

  return (
    <Blueprint className="p-6">
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div className="font-heading font-semibold text-base">Appearance</div>
        <span className="text-[11px] muted-2">White-label</span>
      </div>

      {error && (
        <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-lg text-[13px] mb-4">
          {error}
        </div>
      )}
      {saved && (
        <div className="text-ok bg-[color-mix(in_srgb,var(--ok-raw)_12%,transparent)] px-3 py-2.5 rounded-lg text-[13px] mb-4">
          Appearance saved.
        </div>
      )}

      {/* Identity */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 mb-6">
        <Field label="Product name">
          <input
            className={FIELD}
            value={form.app_name}
            disabled={!canEdit}
            onChange={(e) => set("app_name", e.target.value)}
          />
        </Field>
        <Field label="Short name">
          <input
            className={FIELD}
            value={form.short_name}
            disabled={!canEdit}
            onChange={(e) => set("short_name", e.target.value)}
          />
        </Field>
        <Field label="Tagline">
          <input
            className={FIELD}
            value={form.tagline}
            disabled={!canEdit}
            onChange={(e) => set("tagline", e.target.value)}
          />
        </Field>
        <Field label="Support email">
          <input
            className={FIELD}
            value={form.support_email}
            disabled={!canEdit}
            onChange={(e) => set("support_email", e.target.value)}
          />
        </Field>
      </div>

      {/* Logos */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 mb-6">
        <LogoField
          label="Logo (light theme)"
          value={form.logo_light_data_url}
          disabled={!canEdit}
          onPick={(f) => readFile(f, (d) => set("logo_light_data_url", d))}
          onClear={() => set("logo_light_data_url", "")}
        />
        <LogoField
          label="Logo (dark theme)"
          value={form.logo_dark_data_url}
          disabled={!canEdit}
          onPick={(f) => readFile(f, (d) => set("logo_dark_data_url", d))}
          onClear={() => set("logo_dark_data_url", "")}
        />
      </div>

      {/* Theme tokens */}
      <div className="text-sm font-medium mb-2.5">Theme colours</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-6">
        {(["light_tokens", "dark_tokens"] as const).map((mode) => (
          <div key={mode}>
            <div className="text-xs muted mb-2 capitalize">
              {mode === "light_tokens" ? "Light" : "Dark"} theme
            </div>
            <div className="flex flex-col gap-2">
              {THEME_FIELDS.map((f) => (
                <div key={f.token} className="flex items-center gap-2.5">
                  <input
                    type="color"
                    className="w-9 h-9 rounded-lg border border-divider bg-transparent shrink-0 cursor-pointer disabled:cursor-not-allowed"
                    // An unset token falls back to the stylesheet, so show
                    // THAT — not #000000. `<input type="color">` has no empty
                    // state, so a blank value renders black, which read as
                    // "the background is black" when it was simply unset.
                    value={form[mode][f.token] || DEFAULT_TOKENS[mode][f.token] || "#000000"}
                    disabled={!canEdit}
                    onChange={(e) => setToken(mode, f.token, e.target.value)}
                  />
                  <span className="text-[13px] flex-1">
                    {f.label}
                    {!form[mode][f.token] && (
                      <span className="ml-1.5 text-[11px] muted-3">default</span>
                    )}
                  </span>
                  {form[mode][f.token] && canEdit && (
                    <button
                      type="button"
                      className="text-[11px] muted hover:text-err"
                      onClick={() => {
                        const next = { ...form[mode] };
                        delete next[f.token];
                        setForm({ ...form, [mode]: next });
                      }}
                    >
                      reset
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2.5 mb-7">
        <button
          type="button"
          className="btn btn-filled"
          disabled={!canEdit || saveMut.isPending}
          onClick={() => saveMut.mutate(form)}
        >
          {saveMut.isPending ? "Saving…" : "Save appearance"}
        </button>
        <button
          type="button"
          className="btn btn-outlined"
          disabled={!canEdit}
          onClick={() => data && setForm(data)}
        >
          Discard
        </button>
      </div>

      {/* Dashboard layout */}
      <div className="border-t border-divider pt-5">
        <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
          <div>
            <div className="text-sm font-medium">Dashboard layout</div>
            <div className="text-xs muted">
              Choose which panels appear, how wide they are, and how charts are drawn.
            </div>
          </div>
          <button
            type="button"
            className="btn btn-outlined"
            disabled={!canEdit || resetMut.isPending}
            onClick={() => resetMut.mutate()}
          >
            Reset to default
          </button>
        </div>

        <ul className="flex flex-col gap-1.5 m-0 p-0 list-none">
          {widgets.map((w, i) => (
            <li
              key={w.id}
              className="flex items-center gap-2.5 flex-wrap px-3 py-2.5 rounded-lg border border-divider"
            >
              <div className="flex flex-col">
                <button
                  type="button"
                  aria-label="Move up"
                  className="icobtn muted hover:text-accent disabled:opacity-30 leading-none"
                  disabled={!canEdit || i === 0}
                  onClick={() => move(i, -1)}
                >
                  <Icon name="chevronDown" size={13} />
                </button>
                <button
                  type="button"
                  aria-label="Move down"
                  className="icobtn muted hover:text-accent disabled:opacity-30 leading-none"
                  disabled={!canEdit || i === widgets.length - 1}
                  onClick={() => move(i, 1)}
                >
                  <Icon name="chevronDown" size={13} />
                </button>
              </div>

              <span className="text-[13px] flex-1 min-w-[160px]">
                {WIDGET_LABELS[w.id] ?? w.id}
              </span>

              <label className="text-[12px] muted flex items-center gap-1.5">
                Width
                <select
                  className="eq-field px-2 py-1 text-[12px] bg-transparent border border-divider rounded-md"
                  value={w.span}
                  disabled={!canEdit}
                  onChange={(e) => patchWidget(w.id, { span: Number(e.target.value) })}
                >
                  {[1, 2, 3, 4].map((n) => (
                    <option key={n} value={n}>
                      {n}/4
                    </option>
                  ))}
                </select>
              </label>

              {WIDGET_VIZ[w.id] && (
                <label className="text-[12px] muted flex items-center gap-1.5">
                  Chart
                  <select
                    className="eq-field px-2 py-1 text-[12px] bg-transparent border border-divider rounded-md"
                    value={w.viz ?? ""}
                    disabled={!canEdit}
                    onChange={(e) =>
                      patchWidget(w.id, { viz: e.target.value as VizType })
                    }
                  >
                    {WIDGET_VIZ[w.id]!.map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <label className="text-[12px] muted flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={w.visible}
                  disabled={!canEdit}
                  onChange={(e) => patchWidget(w.id, { visible: e.target.checked })}
                />
                Visible
              </label>
            </li>
          ))}
        </ul>

        {missing.length > 0 && canEdit && (
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            <span className="text-[12px] muted">Add panel:</span>
            {missing.map((id) => (
              <button
                key={id}
                type="button"
                className="btn btn-outlined text-[12px] py-1 px-2.5"
                onClick={() => addWidget(id)}
              >
                <Icon name="plus" size={12} sw={1.8} />
                {WIDGET_LABELS[id]}
              </button>
            ))}
          </div>
        )}
      </div>
    </Blueprint>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[13px] muted mb-2">{label}</label>
      {children}
    </div>
  );
}

function LogoField({
  label,
  value,
  disabled,
  onPick,
  onClear,
}: {
  label: string;
  value: string;
  disabled: boolean;
  onPick: (file: File) => void;
  onClear: () => void;
}) {
  return (
    <Field label={label}>
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-lg border border-divider grid place-items-center overflow-hidden shrink-0 bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]">
          {value ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={value} alt="" className="w-full h-full object-contain" />
          ) : (
            <Icon name="flask" size={18} />
          )}
        </div>
        <input
          type="file"
          accept="image/png,image/jpeg,image/svg+xml,image/webp"
          disabled={disabled}
          className="text-[12px] muted max-w-[190px]"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onPick(file);
          }}
        />
        {value && !disabled && (
          <button type="button" className="text-[12px] muted hover:text-err" onClick={onClear}>
            remove
          </button>
        )}
      </div>
    </Field>
  );
}
