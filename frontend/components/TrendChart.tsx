"use client";

import { useMemo, useState } from "react";

import Blueprint from "@/components/Blueprint";
import { useElementWidth } from "@/components/ui/useElementWidth";
import type { TrendPoint } from "@/lib/api";
import { compact, shortDate } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/**
 * Revenue over time, in whichever form the tenant configured.
 *
 * One series, so there is no legend box — the title names it, and the accent
 * colour is the tenant's own. Grid and axis text stay recessive; values are
 * shown on hover rather than printed on every point.
 */

export type TrendViz = "line" | "area" | "bar";

const H = 220;
const PAD_T = 16;
const PAD_B = 26;
const BAR_RADIUS = 4;
const BAR_GAP = 2; // surface gap between adjacent bars

export default function TrendChart({
  data,
  viz = "area",
  title,
}: {
  data: TrendPoint[];
  viz?: TrendViz;
  title?: string | null;
}) {
  const { t } = useI18n();
  const { ref, width } = useElementWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const max = Math.max(...data.map((d) => d.amount), 1);
  const plotH = H - PAD_T - PAD_B;
  const y = (v: number) => PAD_T + plotH - (v / max) * plotH;
  const baseline = PAD_T + plotH;

  // Line/area sample points sit on the edges; bars are centred in their slot.
  const stepLine = width / Math.max(data.length - 1, 1);
  const slot = width / Math.max(data.length, 1);

  const points = useMemo(
    () => data.map((d, i) => [i * stepLine, y(d.amount)] as const),
    [data, stepLine, max]
  );

  const linePath = points.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} ${width},${baseline} 0,${baseline}`;

  const nearest = (clientX: number, rect: DOMRect) => {
    const x = clientX - rect.left;
    const idx =
      viz === "bar"
        ? Math.floor(x / slot)
        : Math.round(x / stepLine);
    return Math.min(Math.max(idx, 0), data.length - 1);
  };

  const active = hover !== null ? data[hover] : null;
  const activeX =
    hover === null ? 0 : viz === "bar" ? hover * slot + slot / 2 : hover * stepLine;

  return (
    <Blueprint className="p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-[10px] tracking-[0.12em] uppercase text-accent">
            {t("dashboard.trend")}
          </div>
          <div className="font-heading font-semibold text-[17px]">
            {title || t("dashboard.salesRevenue")}
          </div>
        </div>
        <div className="flex gap-4 text-xs items-center">
          <span className="inline-flex items-center gap-1.5">
            <span
              className={
                viz === "bar"
                  ? "w-2.5 h-2.5 rounded-[2px] bg-accent"
                  : "w-2.5 h-0.5 bg-accent"
              }
            />
            {t("dashboard.kpi.revenue")}
          </span>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="py-14 text-center muted-2 text-sm">{t("dashboard.noRevenue")}</div>
      ) : (
        <>
          <div ref={ref} className="relative">
            <svg
              width={width}
              height={H}
              className="block overflow-visible"
              role="img"
              aria-label={`${title || t("dashboard.salesRevenue")} — ${viz} chart`}
              onMouseMove={(e) =>
                setHover(nearest(e.clientX, e.currentTarget.getBoundingClientRect()))
              }
              onMouseLeave={() => setHover(null)}
            >
              {/* Recessive gridlines */}
              {[0, 0.25, 0.5, 0.75, 1].map((f) => (
                <line
                  key={f}
                  x1={0}
                  y1={PAD_T + plotH * f}
                  x2={width}
                  y2={PAD_T + plotH * f}
                  stroke="var(--color-divider)"
                  strokeWidth={1}
                />
              ))}

              {viz === "bar" &&
                data.map((d, i) => {
                  const barW = Math.max(slot - BAR_GAP * 2, 2);
                  const top = y(d.amount);
                  const h = Math.max(baseline - top, 1);
                  return (
                    <rect
                      key={d.date}
                      x={i * slot + BAR_GAP}
                      y={top}
                      width={barW}
                      height={h}
                      rx={Math.min(BAR_RADIUS, barW / 2)}
                      fill="var(--color-accent)"
                      opacity={hover === null || hover === i ? 1 : 0.55}
                    />
                  );
                })}

              {viz === "area" && (
                <polygon
                  points={areaPath}
                  fill="color-mix(in srgb, var(--color-accent) 12%, transparent)"
                />
              )}

              {viz !== "bar" && (
                <polyline
                  points={linePath}
                  fill="none"
                  stroke="var(--color-accent)"
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              )}

              {/* Crosshair + marker on hover */}
              {active && (
                <>
                  <line
                    x1={activeX}
                    y1={PAD_T}
                    x2={activeX}
                    y2={baseline}
                    stroke="var(--m3-outline)"
                    strokeWidth={1}
                  />
                  {viz !== "bar" && (
                    <circle
                      cx={activeX}
                      cy={y(active.amount)}
                      r={5}
                      fill="var(--color-accent)"
                      stroke="var(--color-bg)"
                      strokeWidth={2}
                    />
                  )}
                </>
              )}
            </svg>

            {active && (
              <div
                className="pointer-events-none absolute z-10 px-2.5 py-1.5 rounded-lg border border-divider bg-bg shadow-[var(--shadow-md)] text-xs whitespace-nowrap"
                style={{
                  left: Math.min(Math.max(activeX, 56), Math.max(width - 56, 56)),
                  top: 0,
                  transform: "translate(-50%, -8px)",
                }}
              >
                <span className="muted">{shortDate(active.date)}</span>
                <span className="mx-1.5 text-divider">·</span>
                <span className="font-semibold">{compact(active.amount)}</span>
              </div>
            )}
          </div>

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
