import Blueprint from "@/components/Blueprint";
import { Icon } from "@/components/icons";

export type Delta = { dir: "up" | "down"; text: string; tone: "ok" | "warn" | "err" };

export default function KpiCard({
  icon,
  label,
  value,
  unit = "XAF",
  sub,
  delta,
  spark,
}: {
  icon: string;
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  delta?: Delta;
  spark?: number[];
}) {
  return (
    <Blueprint className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="w-[38px] h-[38px] rounded-lg grid place-items-center bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent">
          <Icon name={icon} size={19} />
        </div>
        {delta && (
          <span
            className={`inline-flex items-center gap-1 text-xs font-semibold ${
              delta.tone === "ok"
                ? "text-ok"
                : delta.tone === "warn"
                ? "text-warn"
                : "text-err"
            }`}
          >
            <Icon name={delta.dir === "up" ? "arrowUp" : "arrowDown"} size={13} sw={2} />
            {delta.text}
          </span>
        )}
      </div>

      <div className="text-[11px] tracking-[0.1em] uppercase muted">{label}</div>
      <div className="font-heading font-semibold text-[28px] leading-[1.1] mt-1 mb-0.5">
        {value} <span className="text-[15px] muted">{unit}</span>
      </div>

      {spark && spark.length > 1 && <Sparkline data={spark} />}
      {sub && <div className="text-[11px] muted-2 mt-0.5">{sub}</div>}
    </Blueprint>
  );
}

function Sparkline({ data }: { data: number[] }) {
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const span = max - min || 1;
  const step = 100 / Math.max(data.length - 1, 1);
  const pts = data
    .map((v, i) => `${(i * step).toFixed(1)},${(24 - ((v - min) / span) * 21).toFixed(1)}`)
    .join(" ");
  return (
    <svg
      width="100%"
      height="26"
      viewBox="0 0 100 26"
      preserveAspectRatio="none"
      className="mt-2 text-accent"
    >
      <polyline fill="none" stroke="currentColor" strokeWidth="1.5" points={pts} />
    </svg>
  );
}
