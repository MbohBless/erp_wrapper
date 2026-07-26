import Blueprint from "@/components/Blueprint";
import type { TrendPoint } from "@/lib/api";
import { shortDate } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const W = 640;
const H = 220;

export default function TrendChart({ data }: { data: TrendPoint[] }) {
  const { t } = useI18n();
  const max = Math.max(...data.map((d) => d.amount), 1);
  const step = W / Math.max(data.length - 1, 1);
  const y = (v: number) => H - 21 - (v / max) * (H - 42);
  const pts = data.map((d, i) => [i * step, y(d.amount)] as const);
  const line = pts.map(([px, py]) => `${px.toFixed(0)},${py.toFixed(0)}`).join(" ");
  const area = `${pts.map(([px, py]) => `${px.toFixed(0)},${py.toFixed(0)}`).join(" ")} ${W},${H - 21} 0,${H - 21}`;

  return (
    <Blueprint className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-[10px] tracking-[0.12em] uppercase text-accent">{t("dashboard.trend")}</div>
          <div className="font-heading font-semibold text-[17px]">
            {t("dashboard.salesRevenue")}
          </div>
        </div>
        <div className="flex gap-4 text-xs items-center">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 bg-accent" />
            {t("dashboard.kpi.revenue")}
          </span>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="py-14 text-center muted-2 text-sm">
          {t("dashboard.noRevenue")}
        </div>
      ) : (
        <>
          <svg
            width="100%"
            height="220"
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="none"
            className="block"
          >
            {[40, 93, 146, 199].map((gy) => (
              <line
                key={gy}
                x1="0"
                y1={gy}
                x2={W}
                y2={gy}
                stroke="var(--color-divider)"
                strokeWidth="1"
              />
            ))}
            <polygon
              points={area}
              fill="color-mix(in srgb, var(--color-accent) 12%, transparent)"
            />
            <polyline
              points={line}
              fill="none"
              stroke="var(--color-accent)"
              strokeWidth="2"
            />
          </svg>
          <div className="flex justify-between text-[11px] muted-3 mt-2">
            {data.map((d) => (
              <span key={d.date}>{shortDate(d.date)}</span>
            ))}
          </div>
        </>
      )}
    </Blueprint>
  );
}
