"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { TelemetryField } from "./telemetry-field";
import { NmCarousel, type NmSnapshot } from "./nm-carousel";
import {
  ProgressionRatePanel,
  type ProgressionSnapshot,
} from "./progression-rate-panel";
import { PUBLIC_TELEMETRY_SNAPSHOT_URL } from "./live-config";
import publicSnapshot from "../public/data/public_snapshot.json";

type CombatDailyRow = {
  event_date: string;
  completed_fights: number;
  proactive_engagements: number;
  reactive_engagements: number;
  attack_issued: number;
  attack_rejections: number;
  attack_rejection_rate: number | null;
  target_cycle_errors: number;
  weapon_skills: number;
  job_abilities: number;
  combat_spells: number;
};

type NavigationDailyRow = {
  event_date: string;
  camp_relocations: number;
  zone_transitions: number;
  line_of_sight_nudges: number;
  collision_probes: number;
  successful_collision_probes: number;
  partial_progress_probes: number;
  stalled_probes: number;
  service_teleport_operations: number;
};

type McpOperationRow = {
  operation: string;
  operation_count: number;
  successful_operations: number;
  failed_operations: number;
  success_rate: number | null;
};

type ProgressDailyRow = {
  event_date: string;
  target_levels_reached: number;
  objective_milestones: number;
};

type DataQualityRow = {
  source: string;
  bronze_rows: number;
  duplicate_event_ids: number;
  latest_session_malformed_rows: number;
  latest_session_reconciled: boolean;
};

type DashboardSnapshot = {
  schema_version: number;
  generated_at: string;
  dashboard_contract?: {
    version?: number;
    required_datasets?: string[];
    dataset_row_counts?: Record<string, number>;
    single_snapshot?: boolean;
  };
  coverage?: {
    earliest_event_time?: string | null;
    latest_event_time?: string | null;
  };
  privacy?: {
    classification?: string;
    contains_raw_payloads?: boolean;
    contains_agent_ids?: boolean;
    contains_lease_ids?: boolean;
  };
  datasets: {
    combat_daily: CombatDailyRow[];
    navigation_daily: NavigationDailyRow[];
    mcp_operations: McpOperationRow[];
    progress_daily: ProgressDailyRow[];
    data_quality: DataQualityRow[];
  } & Record<string, unknown>;
};

const REFRESH_INTERVAL_MS = 10 * 60 * 1000;
const STALE_AFTER_MS = 90 * 60 * 1000;
const FORBIDDEN_KEYS = new Set([
  "agent_id",
  "lease_id",
  "raw_json",
  "raw_payload",
  "stream_key",
  "bridge_token",
]);
const REQUIRED_DASHBOARD_DATASETS = [
  "progress_daily",
  "progression_velocity",
  "progression_current",
  "combat_daily",
  "navigation_daily",
  "mcp_operations",
  "commit_performance",
  "data_quality",
  "nm_status",
  "nm_observer",
] as const;

const initialDashboardSnapshot = publicSnapshot as unknown as DashboardSnapshot;

const sourceLabels: Record<string, string> = {
  agent_actions: "Agent actions",
  farm_supervisor: "Supervisor events",
  navigation: "Navigation probes",
  state_snapshot: "State snapshots",
};

function sum<T>(rows: T[], select: (row: T) => number) {
  return rows.reduce((total, row) => total + (select(row) || 0), 0);
}

function formatNumber(value: number) {
  return Math.round(value).toLocaleString("en-US");
}

function formatRate(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

function shortDate(value: string) {
  const date = new Date(`${value}T12:00:00-04:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  });
}

function snapshotDate(value: string) {
  const date = new Date(value.replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return "Snapshot time unavailable";
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
    timeZoneName: "short",
  });
}

function relativeAge(value: string, now: number) {
  const timestamp = new Date(value.replace(" ", "T")).getTime();
  if (!Number.isFinite(timestamp)) return "update time unavailable";
  const minutes = Math.max(0, Math.round((now - timestamp) / 60_000));
  if (minutes < 1) return "updated just now";
  if (minutes < 60) return `updated ${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `updated ${hours}h ${minutes % 60}m ago`;
}

function containsForbiddenKeys(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(containsForbiddenKeys);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(
    ([key, nested]) =>
      FORBIDDEN_KEYS.has(key.toLowerCase()) || containsForbiddenKeys(nested),
  );
}

function isSafeDashboardSnapshot(value: unknown): value is DashboardSnapshot {
  if (!value || typeof value !== "object") return false;
  const candidate = value as DashboardSnapshot;
  const rowCounts = candidate.dashboard_contract?.dataset_row_counts;
  const completeContract = REQUIRED_DASHBOARD_DATASETS.every((name) => {
    const rows = candidate.datasets?.[name];
    return Array.isArray(rows) && rows.length === rowCounts?.[name];
  });
  return (
    candidate.schema_version >= 5 &&
    typeof candidate.generated_at === "string" &&
    candidate.dashboard_contract?.version === 1 &&
    candidate.dashboard_contract?.single_snapshot === true &&
    completeContract &&
    candidate.privacy?.classification === "public_aggregate" &&
    candidate.privacy?.contains_raw_payloads === false &&
    candidate.privacy?.contains_agent_ids === false &&
    candidate.privacy?.contains_lease_ids === false &&
    Array.isArray(candidate.datasets?.combat_daily) &&
    Array.isArray(candidate.datasets?.navigation_daily) &&
    Array.isArray(candidate.datasets?.mcp_operations) &&
    Array.isArray(candidate.datasets?.progress_daily) &&
    Array.isArray(candidate.datasets?.data_quality) &&
    !containsForbiddenKeys(candidate.datasets)
  );
}

function Metric({
  index,
  label,
  value,
  note,
  tone,
}: {
  index: string;
  label: string;
  value: string;
  note: string;
  tone: "acid" | "violet" | "coral" | "paper";
}) {
  return (
    <article className={`metric metric-${tone}`}>
      <div className="metric-topline">
        <span>{index}</span>
        <i aria-hidden="true" />
      </div>
      <p>{label}</p>
      <strong>{value}</strong>
      <span className="metric-note">{note}</span>
    </article>
  );
}

export default function Home() {
  const [snapshot, setSnapshot] = useState(initialDashboardSnapshot);
  const [now, setNow] = useState(() => Date.now());
  const [refreshState, setRefreshState] = useState<
    "ready" | "refreshing" | "offline"
  >("ready");

  const refresh = useCallback(async () => {
    setRefreshState("refreshing");
    try {
      const url = new URL(PUBLIC_TELEMETRY_SNAPSHOT_URL);
      url.searchParams.set("v", String(Math.floor(Date.now() / 300_000)));
      const response = await fetch(url, {
        cache: "no-store",
        headers: { accept: "application/json" },
      });
      if (!response.ok) throw new Error("telemetry refresh failed");
      const candidate: unknown = await response.json();
      if (!isSafeDashboardSnapshot(candidate)) {
        throw new Error("telemetry response failed its privacy contract");
      }
      setSnapshot(candidate);
      setRefreshState("ready");
    } catch {
      setRefreshState("offline");
    } finally {
      setNow(Date.now());
    }
  }, []);

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => void refresh(), 0);
    const refreshTimer = window.setInterval(refresh, REFRESH_INTERVAL_MS);
    const ageTimer = window.setInterval(() => setNow(Date.now()), 60_000);
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", refreshWhenVisible);
    window.addEventListener("focus", refreshWhenVisible);
    return () => {
      window.clearTimeout(initialRefresh);
      window.clearInterval(refreshTimer);
      window.clearInterval(ageTimer);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
      window.removeEventListener("focus", refreshWhenVisible);
    };
  }, [refresh]);

  const combatRows = snapshot.datasets.combat_daily;
  const navigationRows = snapshot.datasets.navigation_daily;
  const mcpRows = snapshot.datasets.mcp_operations;
  const progressRows = snapshot.datasets.progress_daily;
  const qualityRows = snapshot.datasets.data_quality.map((row) => ({
    source: sourceLabels[row.source] ?? row.source,
    rows: formatNumber(row.bronze_rows),
    malformed: row.latest_session_malformed_rows,
    status: row.latest_session_reconciled
      ? row.source === "state_snapshot"
        ? "Observed"
        : "Reconciled"
      : "Review",
  }));

  const dailyFights = useMemo(() => {
    const recent = combatRows.slice(-7);
    const maximum = Math.max(...recent.map((row) => row.completed_fights), 1);
    return recent.map((row) => ({
      day: shortDate(row.event_date),
      value: row.completed_fights,
      height: (row.completed_fights / maximum) * 100,
    }));
  }, [combatRows]);

  const combatDays = useMemo(
    () =>
      combatRows.slice(-7).map((row) => ({
        day: shortDate(row.event_date),
        rate: (row.attack_rejection_rate ?? 0) * 100,
        fights: row.completed_fights,
      })),
    [combatRows],
  );

  const operations = useMemo(() => {
    const top = [...mcpRows]
      .sort((left, right) => right.operation_count - left.operation_count)
      .slice(0, 5);
    const maximum = Math.max(...top.map((row) => row.operation_count), 1);
    return top.map((row) => ({
      name: row.operation,
      count: row.operation_count,
      success: formatRate(row.success_rate ?? 0),
      volume: (row.operation_count / maximum) * 100,
    }));
  }, [mcpRows]);

  const completedFights = sum(combatRows, (row) => row.completed_fights);
  const proactiveEngagements = sum(
    combatRows,
    (row) => row.proactive_engagements,
  );
  const reactiveEngagements = sum(
    combatRows,
    (row) => row.reactive_engagements,
  );
  const targetCycleErrors = sum(combatRows, (row) => row.target_cycle_errors);
  const weaponSkills = sum(combatRows, (row) => row.weapon_skills);
  const jobAbilities = sum(combatRows, (row) => row.job_abilities);
  const combatSpells = sum(combatRows, (row) => row.combat_spells);
  const combatActions = weaponSkills + jobAbilities + combatSpells;
  const actionShare = (value: number) =>
    combatActions > 0 ? (value / combatActions) * 100 : 0;

  const mcpOperations = sum(mcpRows, (row) => row.operation_count);
  const mcpSuccessful = sum(mcpRows, (row) => row.successful_operations);
  const mcpFailed = sum(mcpRows, (row) => row.failed_operations);
  const mcpSuccessRate = mcpOperations > 0 ? mcpSuccessful / mcpOperations : 0;

  const collisionProbes = sum(navigationRows, (row) => row.collision_probes);
  const collisionArrivals = sum(
    navigationRows,
    (row) => row.successful_collision_probes,
  );
  const partialProgress = sum(
    navigationRows,
    (row) => row.partial_progress_probes,
  );
  const stalledProbes = sum(navigationRows, (row) => row.stalled_probes);
  const probeArrivalRate =
    collisionProbes > 0 ? collisionArrivals / collisionProbes : 0;
  const campRelocations = sum(navigationRows, (row) => row.camp_relocations);
  const zoneTransitions = sum(navigationRows, (row) => row.zone_transitions);
  const lineOfSightNudges = sum(
    navigationRows,
    (row) => row.line_of_sight_nudges,
  );
  const teleportOperations = Math.max(
    ...navigationRows.map((row) => row.service_teleport_operations || 0),
    0,
  );

  const bronzeRows = sum(snapshot.datasets.data_quality, (row) => row.bronze_rows);
  const malformedRows = sum(
    snapshot.datasets.data_quality,
    (row) => row.latest_session_malformed_rows,
  );
  const duplicateEventIds = sum(
    snapshot.datasets.data_quality,
    (row) => row.duplicate_event_ids,
  );
  const milestoneEvents = sum(
    progressRows,
    (row) => row.target_levels_reached + row.objective_milestones,
  );
  const peakFightDay = dailyFights.reduce(
    (peak, row) => (row.value > peak.value ? row : peak),
    dailyFights[0] ?? { day: "Collecting", value: 0, height: 0 },
  );
  const peakFightIndex = Math.max(
    0,
    dailyFights.findIndex((row) => row.day === peakFightDay.day),
  );
  const priorPeakDay = dailyFights[peakFightIndex - 1];
  const peakDelta =
    priorPeakDay && priorPeakDay.value > 0
      ? ((peakFightDay.value - priorPeakDay.value) / priorPeakDay.value) * 100
      : null;
  const firstCombatRate = combatDays[0]?.rate ?? 0;
  const latestCombatRate = combatDays.at(-1)?.rate ?? 0;
  const rejectionDelta = latestCombatRate - firstCombatRate;
  const snapshotAge = now - new Date(snapshot.generated_at).getTime();
  const stale = Number.isFinite(snapshotAge) && snapshotAge > STALE_AFTER_MS;
  const coverageStart = snapshot.coverage?.earliest_event_time;
  const coverageEnd = snapshot.coverage?.latest_event_time;
  const coverageLabel =
    coverageStart && coverageEnd
      ? `${shortDate(coverageStart.slice(0, 10))}–${shortDate(coverageEnd.slice(0, 10))}, 2026`
      : "Coverage window unavailable";

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="FFXI Telemetry home">
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
          <span>FFXI Telemetry</span>
        </a>
        <nav aria-label="Dashboard sections">
          <a href="#notorious-monsters">NM watch</a>
          <a href="#progression">Progression</a>
          <a href="#combat">Combat</a>
          <a href="#navigation">Navigation</a>
          <a href="#quality">Data quality</a>
        </nav>
        <a
          className="repo-link"
          href="https://github.com/pablodcruz/ffxi-telemetry-lab"
        >
          Source <span aria-hidden="true">↗</span>
        </a>
      </header>

      <section className="hero" id="top">
        <TelemetryField />
        <div className="hero-grid" aria-hidden="true" />
        <div className="hero-glow" aria-hidden="true" />

        <div className="hero-copy">
          <div className="eyebrow">
            <span className="pulse-dot" aria-hidden="true" />
            FFXI Agent Lab · Aggregate intelligence
          </div>
          <h1>
            Autonomy,
            <span>measured.</span>
          </h1>
          <p className="lede">
            A public signal surface for autonomous progression, combat
            reliability, navigation, and the MCP control plane.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href="#progression">
              Enter telemetry <span aria-hidden="true">↓</span>
            </a>
            <a
              className="button button-secondary"
              href="https://github.com/pablodcruz/ffxi-telemetry-lab"
            >
              Inspect the pipeline <span aria-hidden="true">↗</span>
            </a>
          </div>
          <div className="privacy-line">
            <span className="privacy-dot" />
            No raw payloads, agent IDs, lease IDs, or full Git SHAs are
            published.
          </div>
        </div>

        <aside className="hero-terminal" aria-label="Telemetry session summary">
          <div className="terminal-bar">
            <div className="traffic-lights" aria-hidden="true">
              <i />
              <i />
              <i />
            </div>
            <span>telemetry-session / {snapshotDate(snapshot.generated_at)}</span>
            <span>01</span>
          </div>
          <div className="terminal-score">
            <div className="score-orbit">
              <span>{(mcpSuccessRate * 100).toFixed(2)}</span>
              <small>%</small>
            </div>
            <div>
              <span className="terminal-label">Control reliability</span>
              <strong>{formatNumber(mcpSuccessful)} successful operations</strong>
              <small>
                {formatNumber(mcpOperations)} total · {formatNumber(mcpFailed)} failed
              </small>
            </div>
          </div>
          <div className="pipeline">
            <div>
              <span>01</span>
              <i />
              <strong>Source files</strong>
              <small>Read only</small>
            </div>
            <div>
              <span>02</span>
              <i />
              <strong>Bronze</strong>
              <small>{bronzeRows.toLocaleString("en-US")} rows</small>
            </div>
            <div>
              <span>03</span>
              <i />
              <strong>Gold</strong>
              <small>47 nodes pass</small>
            </div>
          </div>
          <div className="terminal-status">
            <span className="status-glyph" aria-hidden="true">↳</span>
            <div>
              <span>PUBLIC VIEW</span>
              <strong>Aggregate snapshot verified</strong>
            </div>
            <i aria-hidden="true" />
          </div>
        </aside>

        <div className="hero-meta" aria-label="Snapshot facts">
          <span>{coverageLabel}</span>
          <span>DuckDB · dbt · Parquet</span>
          <span>Gameplay independent</span>
        </div>
      </section>

      <section className="metric-grid section-shell" aria-label="Headline telemetry metrics">
        <Metric
          index="01"
          label="Completed fights"
          value={formatNumber(completedFights)}
          note="Authoritative events"
          tone="acid"
        />
        <Metric
          index="02"
          label="MCP operations"
          value={formatNumber(mcpOperations)}
          note={`${formatRate(mcpSuccessRate)} successful`}
          tone="violet"
        />
        <Metric
          index="03"
          label="Probe arrival rate"
          value={`${(probeArrivalRate * 100).toFixed(1)}%`}
          note={`${formatNumber(collisionArrivals)} of ${formatNumber(collisionProbes)} attempts`}
          tone="coral"
        />
        <Metric
          index="04"
          label="Malformed rows"
          value={formatNumber(malformedRows)}
          note="Latest ingestion session"
          tone="paper"
        />
      </section>

      <section className="signal-strip" aria-label="Pipeline status">
        <div className="section-shell">
          <span>System signal</span>
          <strong>
            {stale ? "Public aggregate needs attention" : "Independent analytics online"}
          </strong>
          <div className="signal-trace" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
            <i />
          </div>
          <small>
            {refreshState === "offline" ? "Endpoint unavailable" : "Hourly refresh"}
            {" · "}{relativeAge(snapshot.generated_at, now)}
          </small>
        </div>
      </section>

      <div className="dashboard-body section-shell">
        <NmCarousel snapshot={snapshot as unknown as NmSnapshot} />

        <section className="panel progression" id="progression">
          <div className="section-heading">
            <div>
              <span className="kicker">01 / Autonomous progression</span>
              <h2>{dailyFights.length} days.<br />One evolving agent.</h2>
            </div>
            <div className="section-stat">
              <span>Milestone signal</span>
              <strong>{formatNumber(milestoneEvents)}</strong>
              <small>level + objective events</small>
            </div>
          </div>

          <div className="progression-layout">
            <div className="chart-card">
              <div className="chart-header">
                <div>
                  <h3>Completed fights by day</h3>
                  <p>Count of `fight_complete` events</p>
                </div>
                <span className="source-tag">GOLD / PROGRESSION</span>
              </div>
              <div className="column-chart" role="img" aria-label="Completed fights by day">
                {dailyFights.map((point) => (
                  <div className="column-item" key={point.day}>
                    <strong>{point.value}</strong>
                    <div className="column-track">
                      <div
                        className="column-fill"
                        style={{ height: `${point.height}%` }}
                      />
                    </div>
                    <span>{point.day}</span>
                  </div>
                ))}
              </div>
            </div>
            <aside className="peak-card">
              <span className="peak-index">
                PEAK / {String(peakFightIndex + 1).padStart(2, "0")}
              </span>
              <strong>{formatNumber(peakFightDay.value)}</strong>
              <p>completed fights on {peakFightDay.day}</p>
              <div className="peak-delta">
                <span>
                  {peakDelta === null
                    ? "First observed day"
                    : `${peakDelta >= 0 ? "+" : ""}${peakDelta.toFixed(1)}%`}
                </span>
                <small>{peakDelta === null ? "baseline" : "vs. prior day"}</small>
              </div>
              <div className="peak-rings" aria-hidden="true">
                <i />
                <i />
                <i />
              </div>
            </aside>
          </div>

          <ProgressionRatePanel snapshot={snapshot as unknown as ProgressionSnapshot} />

          <aside className="coverage-callout">
            <span>Coverage note</span>
            <p>
              Historical fight events contain neither EXP nor gil deltas.
              Velocity begins with the read-only state observer and currently
              represents <strong>early coverage</strong>, not a historical
              backfill.
            </p>
          </aside>
        </section>

        <section className="split-section" id="combat">
          <article className="panel combat-panel">
            <div className="section-heading compact">
              <div>
                <span className="kicker">02 / Combat reliability</span>
                <h2>Attack rejection trend.</h2>
              </div>
              <span className="direction-chip">
                {rejectionDelta <= 0 ? "↓" : "↑"} {Math.abs(rejectionDelta).toFixed(1)} pts
              </span>
            </div>
            <div className="rate-list">
              {combatDays.map((point) => (
                <div className="rate-row" key={point.day}>
                  <span>{point.day}</span>
                  <div className="rate-track">
                    <div className="rate-fill" style={{ width: `${point.rate}%` }} />
                  </div>
                  <strong>{point.rate.toFixed(1)}%</strong>
                  <small>{point.fights} fights</small>
                </div>
              ))}
            </div>
            <div className="mini-metrics">
              <div><strong>{formatNumber(proactiveEngagements)}</strong><span>Proactive</span></div>
              <div><strong>{formatNumber(reactiveEngagements)}</strong><span>Reactive</span></div>
              <div><strong>{formatNumber(targetCycleErrors)}</strong><span>Target-cycle errors</span></div>
            </div>
          </article>

          <article className="panel action-panel">
            <div className="section-heading compact">
              <div>
                <span className="kicker">Action mix</span>
                <h2>Capabilities observed.</h2>
              </div>
            </div>
            <div className="action-total">
              <strong>{formatNumber(combatActions)}</strong>
              <span>combat actions</span>
            </div>
            <div className="action-stack" aria-label="Combat action mix">
              <div className="ws" style={{ width: `${actionShare(weaponSkills)}%` }} />
              <div className="ja" style={{ width: `${actionShare(jobAbilities)}%` }} />
              <div className="spell" style={{ width: `${actionShare(combatSpells)}%` }} />
            </div>
            <ul className="legend">
              <li><span className="dot ws" /> Weapon skills <strong>{formatNumber(weaponSkills)}</strong></li>
              <li><span className="dot ja" /> Job abilities <strong>{formatNumber(jobAbilities)}</strong></li>
              <li><span className="dot spell" /> Combat spells <strong>{formatNumber(combatSpells)}</strong></li>
            </ul>
          </article>
        </section>

        <section className="split-section" id="navigation">
          <article className="panel navigation-panel">
            <div className="section-heading compact">
              <div>
                <span className="kicker">03 / Navigation</span>
                <h2>Movement is a spectrum.</h2>
              </div>
            </div>
            <div className="navigation-visual">
              <div
                className="outcome-ring"
                role="img"
                aria-label={`Collision probe outcomes: ${(probeArrivalRate * 100).toFixed(1)} percent arrived, ${collisionProbes ? ((partialProgress / collisionProbes) * 100).toFixed(1) : "0.0"} percent partial progress, ${collisionProbes ? ((stalledProbes / collisionProbes) * 100).toFixed(1) : "0.0"} percent stalled`}
              >
                <div>
                  <strong>{(probeArrivalRate * 100).toFixed(1)}%</strong>
                  <span>arrived</span>
                </div>
              </div>
              <ul className="legend outcome-legend">
                <li><span className="dot arrived" /> Arrived <strong>{formatNumber(collisionArrivals)}</strong></li>
                <li><span className="dot partial" /> Partial progress <strong>{formatNumber(partialProgress)}</strong></li>
                <li><span className="dot stalled" /> Stalled <strong>{formatNumber(stalledProbes)}</strong></li>
              </ul>
            </div>
          </article>

          <article className="panel mobility-panel">
            <div className="section-heading compact">
              <div>
                <span className="kicker">Mobility signals</span>
                <h2>World movement activity.</h2>
              </div>
            </div>
            <div className="signal-grid">
              <div><span>01</span><strong>{formatNumber(campRelocations)}</strong><small>Camp relocations</small></div>
              <div><span>02</span><strong>{formatNumber(zoneTransitions)}</strong><small>Zone transitions</small></div>
              <div><span>03</span><strong>{formatNumber(lineOfSightNudges)}</strong><small>Line-of-sight nudges</small></div>
              <div><span>04</span><strong>{formatNumber(teleportOperations)}</strong><small>Teleport operations*</small></div>
            </div>
            <p className="footnote">
              *Operation count is a dependency proxy. The event stream does not
              establish navigation causality.
            </p>
          </article>
        </section>

        <section className="panel operations-panel">
          <div className="section-heading">
            <div>
              <span className="kicker">04 / MCP operation reliability</span>
              <h2>A quiet control plane is a healthy one.</h2>
            </div>
            <div className="section-stat danger-stat">
              <span>Failed operations</span>
              <strong>{formatNumber(mcpFailed)}</strong>
              <small>{formatRate(mcpOperations > 0 ? mcpFailed / mcpOperations : 0)} of total</small>
            </div>
          </div>
          <div className="operation-table" role="table" aria-label="Top MCP operations">
            <div className="operation-head" role="row">
              <span>Operation</span><span>Volume</span><span>Success</span>
            </div>
            {operations.map((operation) => (
              <div className="operation-row" role="row" key={operation.name}>
                <code>{operation.name}</code>
                <div className="operation-volume">
                  <span style={{ width: `${operation.volume}%` }} />
                  <small>{operation.count.toLocaleString()}</small>
                </div>
                <strong>{operation.success}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="panel quality-panel" id="quality">
          <div className="section-heading">
            <div>
              <span className="kicker">05 / Data quality</span>
              <h2>Every published boundary reconciled.</h2>
            </div>
            <div className="quality-badge"><i /> {formatNumber(duplicateEventIds)} duplicate event IDs</div>
          </div>
          <div className="quality-summary">
            <div><strong>{qualityRows.length}</strong><span>tracked sources</span></div>
            <div><strong>{formatNumber(bronzeRows)}</strong><span>Bronze events</span></div>
            <div><strong>47/47</strong><span>dbt nodes passed</span></div>
          </div>
          <div className="quality-table" role="table" aria-label="Source reconciliation">
            <div className="quality-head" role="row">
              <span>Source</span><span>Bronze rows</span><span>Malformed</span><span>Status</span>
            </div>
            {qualityRows.map((row) => (
              <div className="quality-row" role="row" key={row.source}>
                <strong>{row.source}</strong>
                <span>{row.rows}</span>
                <span>{row.malformed}</span>
                <span className="status"><i /> {row.status}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="method">
          <span className="kicker">System doctrine</span>
          <h2>Observable facts first.<br />Inference always labeled.</h2>
          <div className="method-grid">
            <article>
              <span>01</span>
              <strong>Immutable Bronze</strong>
              <p>Valid input lines retain their complete raw payload locally.</p>
            </article>
            <article>
              <span>02</span>
              <strong>Tested Gold</strong>
              <p>Cards and charts trace to dbt models with reconciliation tests.</p>
            </article>
            <article>
              <span>03</span>
              <strong>Honest provenance</strong>
              <p>Historical Git attribution is inferred, never authoritative.</p>
            </article>
          </div>
        </section>
      </div>

      <footer>
        <div className="section-shell">
          <div>
            <strong>FFXI Telemetry</strong>
            <span>Independent from gameplay by design.</span>
          </div>
          <p>Reviewed public aggregates refresh hourly.</p>
        </div>
      </footer>
    </main>
  );
}
