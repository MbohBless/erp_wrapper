export type Tone = "ok" | "warn" | "err" | "accent" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  ok: "bg-[color-mix(in_srgb,var(--ok-raw)_15%,transparent)] text-ok",
  warn: "bg-[color-mix(in_srgb,var(--warn-raw)_16%,transparent)] text-warn",
  err: "bg-[color-mix(in_srgb,var(--err-raw)_15%,transparent)] text-err",
  accent: "bg-[color-mix(in_srgb,var(--color-accent)_16%,transparent)] text-accent",
  neutral: "bg-[color-mix(in_srgb,var(--color-text)_10%,transparent)] muted",
};

const TONE_DOT: Record<Tone, string> = {
  ok: "var(--ok-raw)",
  warn: "var(--warn-raw)",
  err: "var(--err-raw)",
  accent: "var(--color-accent)",
  neutral: "currentColor",
};

export default function StatusTag({
  label,
  tone,
  dot = true,
}: {
  label: string;
  tone: Tone;
  dot?: boolean;
}) {
  return (
    <span
      className={`inline-flex items-center text-[11px] px-2.5 py-0.5 rounded-full ${TONE_CLASS[tone]}`}
    >
      {dot && (
        <span
          className="w-1.5 h-1.5 rounded-full mr-1.5"
          style={{ background: TONE_DOT[tone] }}
        />
      )}
      {label}
    </span>
  );
}

/** Active / Disabled tag driven by a boolean. */
export function ActiveTag({ disabled }: { disabled: boolean }) {
  return (
    <StatusTag label={disabled ? "Disabled" : "Active"} tone={disabled ? "neutral" : "ok"} />
  );
}

/** Tone for an ERPNext invoice status (Paid / Overdue / Unpaid…). */
export function invoiceTone(status: string): Tone {
  const s = status.toLowerCase();
  if (s.includes("paid")) return "ok";
  if (s.includes("overdue")) return "err";
  return "warn";
}
