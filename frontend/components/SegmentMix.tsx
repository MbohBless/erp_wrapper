"use client";

import { useState } from "react";

import Blueprint from "@/components/Blueprint";
import { useI18n } from "@/lib/i18n";

/**
 * Revenue composition, in whichever form the tenant configured.
 *
 * Parts of a whole, so the segments are ordered and share one hue stepped from
 * the tenant's accent — a categorical palette is not available here, because
 * the accent itself is white-label configurable. Every segment carries its name
 * and percentage as a direct label, so identity never rests on colour alone.
 */

export type MixViz = "donut" | "progress" | "stacked-bar";

// Revenue-by-segment is illustrative (no per-segment endpoint yet).
const SEGMENTS = [
  { key: "dashboard.segment.hospitals", pct: 52 },
  { key: "dashboard.segment.pharmacies", pct: 26 },
  { key: "dashboard.segment.clinics", pct: 14 },
  { key: "dashboard.segment.ngos", pct: 8 },
];

// One hue, stepped light→dark by rank: a sequential ramp for an ordered
// composition, not a rainbow of unrelated hues.
const SHADES = [100, 72, 48, 28];
const shade = (i: number) =>
  i === 0
    ? "var(--color-accent)"
    : `color-mix(in srgb, var(--color-accent) ${SHADES[i] ?? 20}%, transparent)`;

const DONUT_SIZE = 168;
const DONUT_STROKE = 22;
const GAP_DEG = 2; // surface gap between adjacent arcs

export default function SegmentMix({
  viz = "progress",
  title,
}: {
  viz?: MixViz;
  title?: string | null;
}) {
  const { t } = useI18n();
  const [hover, setHover] = useState<number | null>(null);

  return (
    <Blueprint className="p-5">
      <div className="mb-4">
        <div className="text-[10px] tracking-[0.12em] uppercase text-accent">
          {t("dashboard.mix")}
        </div>
        <div className="font-heading font-semibold text-[17px]">
          {title || t("dashboard.revenueBySegment")}
        </div>
      </div>

      {viz === "donut" && <Donut hover={hover} setHover={setHover} t={t} />}
      {viz === "stacked-bar" && <StackedBar hover={hover} setHover={setHover} t={t} />}
      {viz === "progress" && <Progress hover={hover} setHover={setHover} t={t} />}

      <div className="mt-[18px] pt-3.5 border-t border-divider flex justify-between text-xs muted">
        <span>{t("dashboard.topAccount")}</span>
        <span className="text-ink font-semibold">CHU Yaoundé · 5.6M</span>
      </div>
    </Blueprint>
  );
}

type ViewProps = {
  hover: number | null;
  setHover: (i: number | null) => void;
  t: (key: string) => string;
};

function Legend({ hover, setHover, t }: ViewProps) {
  return (
    <ul className="flex flex-col gap-2 m-0 p-0 list-none">
      {SEGMENTS.map((s, i) => (
        <li
          key={s.key}
          className="flex items-center gap-2 text-[13px] cursor-default"
          onMouseEnter={() => setHover(i)}
          onMouseLeave={() => setHover(null)}
          style={{ opacity: hover === null || hover === i ? 1 : 0.55 }}
        >
          <span
            className="w-2.5 h-2.5 rounded-[3px] shrink-0"
            style={{ background: shade(i) }}
          />
          <span className="flex-1 min-w-0 truncate">{t(s.key)}</span>
          <span className="font-semibold tabular-nums">{s.pct}%</span>
        </li>
      ))}
    </ul>
  );
}

function Donut({ hover, setHover, t }: ViewProps) {
  const r = (DONUT_SIZE - DONUT_STROKE) / 2;
  const circumference = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="flex flex-col items-center gap-4">
      <svg
        width={DONUT_SIZE}
        height={DONUT_SIZE}
        viewBox={`0 0 ${DONUT_SIZE} ${DONUT_SIZE}`}
        role="img"
        aria-label={t("dashboard.revenueBySegment")}
      >
        <g transform={`rotate(-90 ${DONUT_SIZE / 2} ${DONUT_SIZE / 2})`}>
          {SEGMENTS.map((s, i) => {
            // Trim each arc by the gap so neighbours never touch.
            const sweep = (s.pct / 100) * circumference;
            const gap = (GAP_DEG / 360) * circumference;
            const dash = Math.max(sweep - gap, 1);
            const el = (
              <circle
                key={s.key}
                cx={DONUT_SIZE / 2}
                cy={DONUT_SIZE / 2}
                r={r}
                fill="none"
                stroke={shade(i)}
                strokeWidth={DONUT_STROKE}
                strokeDasharray={`${dash} ${circumference - dash}`}
                strokeDashoffset={-offset}
                opacity={hover === null || hover === i ? 1 : 0.55}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              />
            );
            offset += sweep;
            return el;
          })}
        </g>
        <text
          x="50%"
          y="48%"
          textAnchor="middle"
          className="fill-[var(--color-text)] font-heading"
          style={{ fontSize: 24, fontWeight: 600 }}
        >
          {hover === null ? "100%" : `${SEGMENTS[hover].pct}%`}
        </text>
        <text
          x="50%"
          y="62%"
          textAnchor="middle"
          className="fill-[var(--color-text)]"
          style={{ fontSize: 11, opacity: 0.6 }}
        >
          {hover === null ? t("dashboard.mix") : t(SEGMENTS[hover].key)}
        </text>
      </svg>
      <div className="w-full">
        <Legend hover={hover} setHover={setHover} t={t} />
      </div>
    </div>
  );
}

function StackedBar({ hover, setHover, t }: ViewProps) {
  return (
    <div className="flex flex-col gap-4">
      <div
        className="flex h-6 w-full rounded-[4px] overflow-hidden"
        role="img"
        aria-label={t("dashboard.revenueBySegment")}
      >
        {SEGMENTS.map((s, i) => (
          <div
            key={s.key}
            title={`${t(s.key)} · ${s.pct}%`}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            style={{
              width: `${s.pct}%`,
              background: shade(i),
              // 2px surface gap between segments, not a border.
              marginRight: i < SEGMENTS.length - 1 ? 2 : 0,
              opacity: hover === null || hover === i ? 1 : 0.55,
            }}
          />
        ))}
      </div>
      <Legend hover={hover} setHover={setHover} t={t} />
    </div>
  );
}

function Progress({ hover, setHover, t }: ViewProps) {
  return (
    <div className="flex flex-col gap-3.5">
      {SEGMENTS.map((s, i) => (
        <div
          key={s.key}
          onMouseEnter={() => setHover(i)}
          onMouseLeave={() => setHover(null)}
          style={{ opacity: hover === null || hover === i ? 1 : 0.6 }}
        >
          <div className="flex justify-between text-[13px] mb-1.5">
            <span>{t(s.key)}</span>
            <span className="font-semibold tabular-nums">{s.pct}%</span>
          </div>
          <div className="h-2 rounded-[3px] bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
            <div
              className="h-full rounded-[3px]"
              style={{ width: `${s.pct}%`, background: shade(i) }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
