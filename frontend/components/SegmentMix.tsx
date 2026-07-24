import Blueprint from "@/components/Blueprint";

// Revenue-by-segment is illustrative (no per-segment endpoint yet).
const SEGMENTS = [
  { label: "Hospitals", pct: 52, shade: "var(--color-accent)" },
  { label: "Pharmacies", pct: 26, shade: "color-mix(in srgb, var(--color-accent) 70%, transparent)" },
  { label: "Clinics", pct: 14, shade: "color-mix(in srgb, var(--color-accent) 45%, transparent)" },
  { label: "NGOs & programs", pct: 8, shade: "color-mix(in srgb, var(--color-accent) 28%, transparent)" },
];

export default function SegmentMix() {
  return (
    <Blueprint className="p-5">
      <div className="mb-4">
        <div className="text-[10px] tracking-[0.12em] uppercase text-accent">Mix</div>
        <div className="font-heading font-semibold text-[17px]">Revenue by segment</div>
      </div>
      <div className="flex flex-col gap-3.5">
        {SEGMENTS.map((s) => (
          <div key={s.label}>
            <div className="flex justify-between text-[13px] mb-1.5">
              <span>{s.label}</span>
              <span className="font-semibold">{s.pct}%</span>
            </div>
            <div className="h-2 bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
              <div className="h-full" style={{ width: `${s.pct}%`, background: s.shade }} />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-[18px] pt-3.5 border-t border-divider flex justify-between text-xs muted">
        <span>Top account</span>
        <span className="text-ink font-semibold">CHU Yaoundé · 5.6M</span>
      </div>
    </Blueprint>
  );
}
