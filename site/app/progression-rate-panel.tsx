"use client";

import { useEffect, useMemo, useState } from "react";

export type ProgressionGrain = "hour" | "day" | "week";

export type ProgressionVelocityRow = {
  active_seconds: number;
  exp_earned: number;
  exp_per_active_hour: number;
  gil_earned: number;
  gil_per_active_hour: number;
  is_complete: boolean;
  observed_intervals: number;
  period_end: string;
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

export type ProgressionSnapshot = {
  generated_at: string;
  datasets: {
    progression_current: ProgressionCurrentRow[];
    progression_velocity: ProgressionVelocityRow[];
  };
};

type MetricKey = "exp" | "gil";

const STALE_AFTER_MS = 90 * 60 * 1000;

const grains: Array<{ value: ProgressionGrain; label: string }> = [
  { value: "hour", label: "Hour" },
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
];

function number(value: number | null) {
  if (value === null || !Number.isFinite(value)) return "Collecting";
  return Math.round(value).toLocaleString("en-US");
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

function relativeAge(value: string, now: number) {
  const timestamp = dateFromSnapshot(value).getTime();
  if (!Number.isFinite(timestamp)) return "Update time unavailable";
  const minutes = Math.max(0, Math.round((now - timestamp) / 60000));
  if (minutes < 1) return "Updated just now";
  if (minutes < 60) return `Updated ${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return `Updated ${hours}h${remainder ? ` ${remainder}m` : ""} ago`;
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
          <span>{label} velocity · completed periods</span>
          <strong>{label} per active hour</strong>
        </div>
        <i aria-hidden="true" />
      </div>
      <div
        className="velocity-bars"
        role="img"
        aria-label={`${label} per active hour across ${rows.length} completed periods`}
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
  snapshot,
}: {
  snapshot: ProgressionSnapshot;
}) {
  const [grain, setGrain] = useState<ProgressionGrain>("hour");
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const ageTimer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => {
      window.clearInterval(ageTimer);
    };
  }, []);

  const rows = snapshot.datasets.progression_velocity;
  const selected = useMemo(
    () => rows.filter((row) => row.period_grain === grain),
    [grain, rows],
  );
  const completed = selected.filter((row) => row.is_complete === true);
  const currentPeriod =
    selected.filter((row) => !row.is_complete).at(-1) ?? null;
  const latestObservation =
    snapshot.datasets.progression_current[0]?.observed_at ?? snapshot.generated_at;
  const ageMilliseconds = now - dateFromSnapshot(latestObservation).getTime();
  const stale = Number.isFinite(ageMilliseconds) && ageMilliseconds > STALE_AFTER_MS;
  const periodName = grain === "hour" ? "hour" : grain === "day" ? "day" : "week";

  return (
    <section className="velocity-panel" aria-labelledby="velocity-title">
      <div className="velocity-heading">
        <div>
          <span className="kicker">Progression velocity</span>
          <h3 id="velocity-title">EXP and gil, normalized by active time.</h3>
          <p>
            The current period stays separate from completed comparisons.
            Public aggregates refresh hourly without rebuilding this site.
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

      <div
        className={`velocity-freshness ${stale ? "is-stale" : ""}`}
        role="status"
      >
        <i aria-hidden="true" />
        <strong>{relativeAge(latestObservation, now)}</strong>
        <span>
          {stale
            ? "The local feed is stale; the last verified values remain visible."
            : "Hourly public feed verified."}
        </span>
      </div>

      <div className="velocity-kpis">
        <div>
          <span>Current {periodName} EXP/hour</span>
          <strong>{number(currentPeriod?.exp_per_active_hour ?? null)}</strong>
          <small>{number(currentPeriod?.exp_earned ?? null)} EXP so far</small>
        </div>
        <div>
          <span>Current {periodName} gil/hour</span>
          <strong>{number(currentPeriod?.gil_per_active_hour ?? null)}</strong>
          <small>{number(currentPeriod?.gil_earned ?? null)} gil so far</small>
        </div>
        <div>
          <span>Current {periodName} coverage</span>
          <strong>
            {currentPeriod
              ? `${Math.round(currentPeriod.active_seconds / 60)}m`
              : "Collecting"}
          </strong>
          <small>observed active elapsed time</small>
        </div>
        <div>
          <span>Completed {periodName}s</span>
          <strong>{completed.length.toLocaleString("en-US")}</strong>
          <small>stable comparison buckets</small>
        </div>
      </div>

      {completed.length ? (
        <div className="velocity-grid">
          <RateChart rows={completed} metric="exp" />
          <RateChart rows={completed} metric="gil" />
        </div>
      ) : (
        <div className="velocity-empty">
          <strong>Collecting the first completed {periodName}.</strong>
          <span>
            Current progress remains visible above. Completed periods appear
            after the hourly publisher closes their boundary.
          </span>
        </div>
      )}

      <div className="velocity-method">
        <span>Method</span>
        <p>
          Weighted rate = summed counter delta ÷ summed active elapsed-time
          delta × 3,600. Counter resets, non-positive active time, and observer
          gaps over 75 minutes are excluded.
        </p>
      </div>
    </section>
  );
}
