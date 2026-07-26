"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import Blueprint from "@/components/Blueprint";
import { Icon } from "@/components/icons";
import { type CompanyProfile, getCompanyProfile, updateCompanyProfile } from "@/lib/company";

const FIELD = "eq-field w-full px-3 py-2.5 text-sm";
const LABEL = "block text-[13px] muted mb-1.5";
const MAX_LOGO_BYTES = 400_000;

const FIELDS: { key: keyof CompanyProfile; label: string; span?: boolean; placeholder?: string }[] = [
  { key: "legal_name", label: "Registered name", placeholder: "EquiMed SA" },
  { key: "display_name", label: "Display name", placeholder: "EquiMed" },
  { key: "tagline", label: "Tagline", span: true, placeholder: "Medical Equipment Distribution" },
  { key: "address_line", label: "Address", span: true, placeholder: "Bonanjo, Rue …" },
  { key: "city", label: "City", placeholder: "Douala" },
  { key: "country", label: "Country", placeholder: "Cameroon" },
  { key: "phone", label: "Phone", placeholder: "+237 …" },
  { key: "email", label: "Email", placeholder: "contact@equimed.cm" },
  { key: "website", label: "Website", placeholder: "www.equimed.cm" },
  { key: "currency", label: "Currency", placeholder: "XAF" },
  { key: "rc_number", label: "RC number", placeholder: "RC/DLA/…" },
  { key: "niu", label: "NIU (tax ID)", placeholder: "M…" },
  { key: "signatory_name", label: "Signatory name", placeholder: "Full name" },
  { key: "signatory_title", label: "Signatory title", placeholder: "Managing Director" },
];

export default function CompanyBrandingSection({ token, canEdit }: { token: string; canEdit: boolean }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const { data } = useQuery({ queryKey: ["company-profile"], queryFn: () => getCompanyProfile(token) });

  const [form, setForm] = useState<CompanyProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data && !form) setForm(data);
  }, [data, form]);

  const set = <K extends keyof CompanyProfile>(k: K, v: CompanyProfile[K]) => {
    setSaved(false);
    setForm((f) => (f ? { ...f, [k]: v } : f));
  };

  const save = useMutation({
    mutationFn: () => updateCompanyProfile(token, form as CompanyProfile),
    onSuccess: (res) => {
      setForm(res);
      setSaved(true);
      setError(null);
      qc.invalidateQueries({ queryKey: ["company-profile"] });
    },
    onError: (e) => setError(e instanceof Error ? e.message : "Failed to save"),
  });

  function onLogo(file: File | undefined) {
    if (!file) return;
    if (file.size > MAX_LOGO_BYTES) {
      setError("Logo must be under 400 KB. Try a smaller PNG/JPG.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => set("logo_data_url", String(reader.result));
    reader.readAsDataURL(file);
  }

  if (!form) {
    return (
      <Blueprint className="p-6">
        <div className="muted-2 text-sm">Loading branding…</div>
      </Blueprint>
    );
  }

  const disabled = !canEdit;

  return (
    <Blueprint className="p-6">
      <div className="flex items-center justify-between mb-1.5 gap-4">
        <div className="font-heading font-semibold text-base">Company &amp; branding</div>
        <span className="text-[11px] muted-2">Used on report letterheads</span>
      </div>
      <p className="muted text-[13px] mb-5">
        These details appear on the branded, digitally-signed PDF reports.
      </p>

      {/* Logo + accent */}
      <div className="flex flex-wrap items-center gap-5 mb-6">
        <div className="w-[104px] h-[104px] rounded-xl border border-divider grid place-items-center overflow-hidden bg-[color-mix(in_srgb,var(--color-text)_3%,transparent)] shrink-0">
          {form.logo_data_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={form.logo_data_url} alt="Logo" className="max-w-full max-h-full object-contain" />
          ) : (
            <span className="muted-3 text-xs text-center px-2">No logo</span>
          )}
        </div>
        <div className="flex flex-col gap-2">
          {canEdit && (
            <div className="flex items-center gap-2">
              <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/svg+xml" className="hidden" onChange={(e) => onLogo(e.target.files?.[0])} />
              <button type="button" onClick={() => fileRef.current?.click()} className="btn btn-outlined">Upload logo</button>
              {form.logo_data_url && (
                <button type="button" onClick={() => set("logo_data_url", "")} className="btn btn-text">Remove</button>
              )}
            </div>
          )}
          <label className="flex items-center gap-2.5 text-sm">
            <span className={LABEL + " mb-0"}>Accent colour</span>
            <input type="color" value={form.accent_color || "#416180"} disabled={disabled} onChange={(e) => set("accent_color", e.target.value)} className="w-9 h-9 rounded border border-divider bg-transparent p-0.5 disabled:opacity-60" />
            <span className="text-xs muted num">{form.accent_color}</span>
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-4">
        {FIELDS.map((f) => (
          <div key={f.key} className={f.span ? "sm:col-span-2" : ""}>
            <label className={LABEL}>{f.label}</label>
            <input
              className={FIELD}
              value={(form[f.key] as string) ?? ""}
              placeholder={f.placeholder}
              disabled={disabled}
              onChange={(e) => set(f.key, e.target.value as CompanyProfile[typeof f.key])}
            />
          </div>
        ))}
      </div>

      {error && (
        <div className="text-err bg-[color-mix(in_srgb,var(--err-raw)_12%,transparent)] px-3 py-2.5 rounded-xl text-[13px] mt-5">{error}</div>
      )}

      {canEdit && (
        <div className="flex items-center justify-end gap-3 mt-6">
          {saved && <span className="text-[13px] text-ok inline-flex items-center gap-1"><Icon name="check" size={14} sw={2.2} /> Saved</span>}
          <button type="button" onClick={() => save.mutate()} disabled={save.isPending} className="btn btn-filled">
            {save.isPending ? "Saving…" : "Save branding"}
          </button>
        </div>
      )}
    </Blueprint>
  );
}
