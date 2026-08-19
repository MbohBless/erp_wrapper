"use client";

import { useState } from "react";

import Blueprint from "@/components/Blueprint";
import { compact } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/**
 * Revenue composition, in whichever form the tenant configured.
 *
 * Segments come from submitted invoices grouped by ERPNext Customer Group.
 * This panel previously rendered a fixed 52/26/14/8 split with a named "top
 * account" — invented numbers that read as analysis. With no invoices it now
 * shows an empty state, which is the honest answer.
 *
 * Parts of a whole, so the segments are ordered and share one hue stepped from
 * the tenant's accent — a categorical palette is not available here, because
 * the accent itself is white-label configurable. Every segment carries its name
 * and percentage as a direct label, so identity never rests on colour alone.
 */

export type MixViz = "donut" | "progress" | "stacked-bar";

export type Segment = { label: string; amount: number; pct: number };

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

type ViewProps = {
  segments: Segment[];
  hover: number | null;
  setHover: (i: number | null) => void;
  t: (key: string) => string;
};

export default function SegmentMix({
  viz = "progress",
  title,
  segments = [],
  topCustomer = null,
}: {
  viz?: MixViz;
  title?: string | null;
  /** Real revenue split, from submitted invoices. Empty until there are any. */
  segments?: Segment[];
  topCustomer?: { label: string; amount: number } | null;
}) {
  const { t } = useI18n();
  const [hover, setHover] = useState<number | null>(null);
  const view: ViewProps = { segments, hover, setHover, t };

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

      {segments.length === 0 ? (
        <div className="py-12 text-center muted-2 text-sm">
          {t("dashboard.noSegments")}
        </div>
      ) : (
        <>
          {viz === "donut" && <Donut {...view} />}
          {viz === "stacked-bar" && <StackedBar {...view} />}
          {viz === "progress" && <Progress {...view} />}
        </>
      )}

      {topCustomer && (
        <div className="mt-[18px] pt-3.5 border-t border-divider flex justify-between text-xs muted gap-3">
          <span className="shrink-0">{t("dashboard.topAccount")}</span>
          <span className="text-ink font-semibold truncate">
            {topCustomer.label} · {compact(topCustomer.amount)}
          </span>
        </div>
      )}
    </Blueprint>
  );
}

function Legend({ segments, hover, setHover }: ViewProps) {
  return (
    <ul className="flex flex-col gap-2 m-0 p-0 list-none">
      {segments.map((s, i) => (
        <li
          key={s.label}
          className="flex items-center gap-2 text-[13px] cursor-default"
          onMouseEnter={() => setHover(i)}
          onMouseLeave={() => setHover(null)}
          style={{ opacity: hover === null || hover === i ? 1 : 0.55 }}
        >
          <span
            className="w-2.5 h-2.5 rounded-[3px] shrink-0"
            style={{ background: shade(i) }}
          />
          <span className="flex-1 min-w-0 truncate">{s.label}</span>
          <span className="font-semibold tabular-nums">{s.pct}%</span>
        </li>
      ))}
    </ul>
  );
}

function Donut(props: ViewProps) {
  const { segments, hover, setHover, t } = props;
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
          {segments.map((s, i) => {
            // Trim each arc by the gap so neighbours never touch.
            const sweep = (s.pct / 100) * circumference;
            const gap = (GAP_DEG / 360) * circumference;
            const dash = Math.max(sweep - gap, 1);
            const el = (
              <circle
                key={s.label}
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
          {hover === null ? "100%" : `${segments[hover].pct}%`}
        </text>
        <text
          x="50%"
          y="62%"
          textAnchor="middle"
          className="fill-[var(--color-text)]"
          style={{ fontSize: 11, opacity: 0.6 }}
        >
          {hover === null ? t("dashboard.mix") : segments[hover].label}
        </text>
      </svg>
      <div className="w-full">
        <Legend {...props} />
      </div>
    </div>
  );
}

function StackedBar(props: ViewProps) {
  const { segments, hover, setHover, t } = props;
  return (
    <div className="flex flex-col gap-4">
      <div
        className="flex h-6 w-full rounded-[4px] overflow-hidden"
        role="img"
        aria-label={t("dashboard.revenueBySegment")}
      >
        {segments.map((s, i) => (
          <div
            key={s.label}
            title={`${s.label} · ${s.pct}%`}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            style={{
              width: `${s.pct}%`,
              background: shade(i),
              // 2px surface gap between segments, not a border.
              marginRight: i < segments.length - 1 ? 2 : 0,
              opacity: hover === null || hover === i ? 1 : 0.55,
            }}
          />
        ))}
      </div>
      <Legend {...props} />
    </div>
  );
}

function Progress({ segments, hover, setHover }: ViewProps) {
  return (
    <div className="flex flex-col gap-3.5">
      {segments.map((s, i) => (
        <div
          key={s.label}
          onMouseEnter={() => setHover(i)}
          onMouseLeave={() => setHover(null)}
          style={{ opacity: hover === null || hover === i ? 1 : 0.6 }}
        >
          <div className="flex justify-between text-[13px] mb-1.5 gap-3">
            <span className="truncate">{s.label}</span>
            <span className="font-semibold tabular-nums shrink-0">{s.pct}%</span>
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
