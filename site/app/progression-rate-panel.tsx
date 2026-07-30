"use client";

import { useMemo, useState } from "react";

export type ProgressionGrain = "hour" | "day" | "week";

export type ProgressionVelocityRow = {
  active_seconds: number;
  exp_earned: number;
  exp_per_active_hour: number;
  gil_earned: number;
  gil_per_active_hour: number;
  observed_intervals: number;
  period_grain: ProgressionGrain;
  period_start: string;
};

export type ProgressionCurrentRow = {
  elapsed_seconds: number | null;
  lease_exp_earned: number | null;
  lease_exp_per_active_hour: number | null;
  lease_gil_earned: number | null;
  lease_gil_per_active_hour: number | null;
  metric_quality: string;
  observed_at: string;
};

type MetricKey = "exp" | "gil";

const grains: Array<{ value: ProgressionGrain; label: string }> = [
  { value: "hour", label: "Hour" },
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
];

function number(value: number | null, suffix = "") {
  if (value === null || !Number.isFinite(value)) return "Collecting";
  return `${Math.round(value).toLocaleString("en-US")}${suffix}`;
}

function dateFromSnapshot(value: string) {
  const normalized = value
    .replace(" ", "T")
    .replace(/([+-]\d{2})$/, "$1:00");
  return new Date(normalized);
}

function periodLabel(value: string, grain: ProgressionGrain) {
  const date = dateFromSnapshot(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  const base = date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  });
  if (grain === "week") return `Week of ${base}`;
  if (grain === "day") return base;
  return `${base} · ${date.toLocaleTimeString("en-US", {
    hour: "numeric",
    timeZone: "America/New_York",
  })}`;
}

function RateChart({
  rows,
  metric,
}: {
  rows: ProgressionVelocityRow[];
  metric: MetricKey;
}) {
  const isExp = metric === "exp";
  const rateKey = isExp ? "exp_per_active_hour" : "gil_per_active_hour";
  const totalKey = isExp ? "exp_earned" : "gil_earned";
  const maximum = Math.max(...rows.map((row) => row[rateKey]), 1);
  const label = isExp ? "EXP" : "Gil";

  return (
    <article className={`velocity-chart velocity-${metric}`}>
      <div className="velocity-chart-head">
        <div>
          <span>{label} velocity</span>
          <strong>{label} per active hour</strong>
        </div>
        <i aria-hidden="true" />
      </div>
      <div
        className="velocity-bars"
        role="img"
        aria-label={`${label} per active hour across ${rows.length} observed periods`}
      >
        {rows.map((row) => {
          const rate = row[rateKey];
          const total = row[totalKey];
          const height = rate === 0 ? 0 : Math.max((rate / maximum) * 100, 4);
          return (
            <div className="velocity-point" key={`${row.period_grain}-${row.period_start}`}>
              <span className="velocity-value">{number(rate)}</span>
              <div className="velocity-track">
                <div className="velocity-fill" style={{ height: `${height}%` }} />
              </div>
              <span className="velocity-period">
                {periodLabel(row.period_start, row.period_grain)}
              </span>
              <small>
                {number(total)} total · {Math.round(row.active_seconds / 60)}m active
              </small>
            </div>
          );
        })}
      </div>
    </article>
  );
}

export function ProgressionRatePanel({
  rows,
  current,
}: {
  rows: ProgressionVelocityRow[];
  current: ProgressionCurrentRow | null;
}) {
  const [grain, setGrain] = useState<ProgressionGrain>("hour");
  const selected = useMemo(
    () => rows.filter((row) => row.period_grain === grain),
    [grain, rows],
  );

  return (
    <section className="velocity-panel" aria-labelledby="velocity-title">
      <div className="velocity-heading">
        <div>
          <span className="kicker">Progression velocity</span>
          <h3 id="velocity-title">EXP and gil, normalized by active time.</h3>
          <p>
            Totals show what the agent earned. Rates divide those totals by
            observed active supervisor time—hourly rates are never summed.
          </p>
        </div>
        <div className="grain-control" aria-label="Progression time grain">
          {grains.map((option) => (
            <button
              aria-pressed={grain === option.value}
              key={option.value}
              onClick={() => setGrain(option.value)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="velocity-kpis">
        <div>
          <span>Current lease EXP/hour</span>
          <strong>{number(current?.lease_exp_per_active_hour ?? null)}</strong>
          <small>{number(current?.lease_exp_earned ?? null)} EXP observed</small>
        </div>
        <div>
          <span>Current lease gil/hour</span>
          <strong>{number(current?.lease_gil_per_active_hour ?? null)}</strong>
          <small>{number(current?.lease_gil_earned ?? null)} gil observed</small>
        </div>
        <div>
          <span>Trend coverage</span>
          <strong>
            {selected.length
              ? `${Math.round(
                  selected.reduce((sum, row) => sum + row.active_seconds, 0) / 60,
                )}m`
              : "Collecting"}
          </strong>
          <small>active elapsed time in this view</small>
        </div>
      </div>

      {selected.length ? (
        <div className="velocity-grid">
          <RateChart rows={selected} metric="exp" />
          <RateChart rows={selected} metric="gil" />
        </div>
      ) : (
        <div className="velocity-empty">
          <strong>Collecting a trustworthy baseline.</strong>
          <span>
            This grain appears after consecutive snapshots exist in the same
            lease. Gaps over five minutes and counter resets are excluded.
          </span>
        </div>
      )}

      <div className="velocity-method">
        <span>Method</span>
        <p>
          Weighted rate = summed counter delta ÷ summed active elapsed-time
          delta × 3,600. Minute grain is intentionally omitted from the public
          view because short combat bursts make it unstable.
        </p>
      </div>
    </section>
  );
}
