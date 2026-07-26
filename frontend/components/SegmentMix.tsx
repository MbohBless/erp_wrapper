import Blueprint from "@/components/Blueprint";
import { useI18n } from "@/lib/i18n";

// Revenue-by-segment is illustrative (no per-segment endpoint yet).
const SEGMENTS = [
  { key: "dashboard.segment.hospitals", pct: 52, shade: "var(--color-accent)" },
  { key: "dashboard.segment.pharmacies", pct: 26, shade: "color-mix(in srgb, var(--color-accent) 70%, transparent)" },
  { key: "dashboard.segment.clinics", pct: 14, shade: "color-mix(in srgb, var(--color-accent) 45%, transparent)" },
  { key: "dashboard.segment.ngos", pct: 8, shade: "color-mix(in srgb, var(--color-accent) 28%, transparent)" },
];

export default function SegmentMix() {
  const { t } = useI18n();
  return (
    <Blueprint className="p-5">
      <div className="mb-4">
        <div className="text-[10px] tracking-[0.12em] uppercase text-accent">{t("dashboard.mix")}</div>
        <div className="font-heading font-semibold text-[17px]">{t("dashboard.revenueBySegment")}</div>
      </div>
      <div className="flex flex-col gap-3.5">
        {SEGMENTS.map((s) => (
          <div key={s.key}>
            <div className="flex justify-between text-[13px] mb-1.5">
              <span>{t(s.key)}</span>
              <span className="font-semibold">{s.pct}%</span>
            </div>
            <div className="h-2 bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
              <div className="h-full" style={{ width: `${s.pct}%`, background: s.shade }} />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-[18px] pt-3.5 border-t border-divider flex justify-between text-xs muted">
        <span>{t("dashboard.topAccount")}</span>
        <span className="text-ink font-semibold">CHU Yaoundé · 5.6M</span>
      </div>
    </Blueprint>
  );
}
