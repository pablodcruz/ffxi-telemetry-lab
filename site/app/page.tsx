import { TelemetryField } from "./telemetry-field";
import {
  ProgressionRatePanel,
  type ProgressionCurrentRow,
  type ProgressionVelocityRow,
} from "./progression-rate-panel";
import publicSnapshot from "../public/data/public_snapshot.json";

const dailyFights = [
  { day: "Jul 28", value: 68, height: 10 },
  { day: "Jul 29", value: 707, height: 100 },
  { day: "Jul 30", value: 470, height: 66.5 },
];

const combatDays = [
  { day: "Jul 28", rate: 30.2, fights: 68 },
  { day: "Jul 29", rate: 22.6, fights: 707 },
  { day: "Jul 30", rate: 21.7, fights: 470 },
];

const operations = [
  { name: "enable_control", count: 12219, success: "99.88%", volume: 100 },
  { name: "gameplay_command", count: 7962, success: "97.94%", volume: 65.2 },
  { name: "target_entity", count: 5422, success: "96.85%", volume: 44.4 },
  { name: "clear_target", count: 5096, success: "100%", volume: 41.7 },
  { name: "emergency_stop", count: 3650, success: "99.62%", volume: 29.9 },
];

const sourceLabels: Record<string, string> = {
  agent_actions: "Agent actions",
  farm_supervisor: "Supervisor events",
  navigation: "Navigation probes",
  state_snapshot: "State snapshots",
};

const qualityRows = publicSnapshot.datasets.data_quality.map((row) => ({
  source: sourceLabels[row.source] ?? row.source,
  rows: row.bronze_rows.toLocaleString("en-US"),
  malformed: row.latest_session_malformed_rows,
  status: row.source === "state_snapshot" ? "Observed" : "Reconciled",
}));

const bronzeRows = publicSnapshot.datasets.data_quality.reduce(
  (total, row) => total + row.bronze_rows,
  0,
);

const generatedAt = new Date(publicSnapshot.generated_at);
const generatedDate = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
}).format(generatedAt);
const generatedTime = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
}).format(generatedAt);

const progressionVelocity =
  publicSnapshot.datasets.progression_velocity as ProgressionVelocityRow[];
const progressionCurrent =
  (publicSnapshot.datasets.progression_current[0] as ProgressionCurrentRow | undefined) ??
  null;

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
            <span>telemetry-session / 2026-07-30</span>
            <span>01</span>
          </div>
          <div className="terminal-score">
            <div className="score-orbit">
              <span>98.35</span>
              <small>%</small>
            </div>
            <div>
              <span className="terminal-label">Control reliability</span>
              <strong>46,316 successful operations</strong>
              <small>47,094 total · 778 failed</small>
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
          <span>Jul 25–30, 2026</span>
          <span>DuckDB · dbt · Parquet</span>
          <span>Gameplay independent</span>
        </div>
      </section>

      <section className="metric-grid section-shell" aria-label="Headline telemetry metrics">
        <Metric
          index="01"
          label="Completed fights"
          value="1,245"
          note="Authoritative events"
          tone="acid"
        />
        <Metric
          index="02"
          label="MCP operations"
          value="47,094"
          note="98.35% successful"
          tone="violet"
        />
        <Metric
          index="03"
          label="Probe arrival rate"
          value="55.1%"
          note="76 of 138 attempts"
          tone="coral"
        />
        <Metric
          index="04"
          label="Malformed rows"
          value="0"
          note="Frozen backfill boundary"
          tone="paper"
        />
      </section>

      <section className="signal-strip" aria-label="Pipeline status">
        <div className="section-shell">
          <span>System signal</span>
          <strong>Independent analytics online</strong>
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
          <small>Snapshot · {generatedTime} UTC</small>
        </div>
      </section>

      <div className="dashboard-body section-shell">
        <section className="panel progression" id="progression">
          <div className="section-heading">
            <div>
              <span className="kicker">01 / Autonomous progression</span>
              <h2>Three days.<br />One accelerating agent.</h2>
            </div>
            <div className="section-stat">
              <span>Milestone signal</span>
              <strong>10</strong>
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
              <span className="peak-index">PEAK / 02</span>
              <strong>707</strong>
              <p>completed fights on Jul 29</p>
              <div className="peak-delta">
                <span>+939.7%</span>
                <small>vs. prior day</small>
              </div>
              <div className="peak-rings" aria-hidden="true">
                <i />
                <i />
                <i />
              </div>
            </aside>
          </div>

          <ProgressionRatePanel
            rows={progressionVelocity}
            current={progressionCurrent}
          />

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
                <h2>Rejection is trending down.</h2>
              </div>
              <span className="direction-chip">↓ 8.5 pts</span>
            </div>
            <div className="rate-list">
              {combatDays.map((point) => (
                <div className="rate-row" key={point.day}>
                  <span>{point.day}</span>
                  <div className="rate-track">
                    <div className="rate-fill" style={{ width: `${point.rate}%` }} />
                  </div>
                  <strong>{point.rate}%</strong>
                  <small>{point.fights} fights</small>
                </div>
              ))}
            </div>
            <div className="mini-metrics">
              <div><strong>1,509</strong><span>Proactive</span></div>
              <div><strong>312</strong><span>Reactive</span></div>
              <div><strong>68</strong><span>Target-cycle errors</span></div>
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
              <strong>1,037</strong>
              <span>combat actions</span>
            </div>
            <div className="action-stack" aria-label="Combat action mix">
              <div className="ws" style={{ width: "50.1%" }} />
              <div className="ja" style={{ width: "35.1%" }} />
              <div className="spell" style={{ width: "14.8%" }} />
            </div>
            <ul className="legend">
              <li><span className="dot ws" /> Weapon skills <strong>520</strong></li>
              <li><span className="dot ja" /> Job abilities <strong>364</strong></li>
              <li><span className="dot spell" /> Combat spells <strong>153</strong></li>
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
                aria-label="Collision probe outcomes: 55.1 percent arrived, 30.4 percent partial progress, 14.5 percent stalled"
              >
                <div>
                  <strong>55.1%</strong>
                  <span>arrived</span>
                </div>
              </div>
              <ul className="legend outcome-legend">
                <li><span className="dot arrived" /> Arrived <strong>76</strong></li>
                <li><span className="dot partial" /> Partial progress <strong>42</strong></li>
                <li><span className="dot stalled" /> Stalled <strong>20</strong></li>
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
              <div><span>01</span><strong>275</strong><small>Camp relocations</small></div>
              <div><span>02</span><strong>10</strong><small>Zone transitions</small></div>
              <div><span>03</span><strong>89</strong><small>Line-of-sight nudges</small></div>
              <div><span>04</span><strong>964</strong><small>Teleport operations*</small></div>
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
              <strong>778</strong>
              <small>1.65% of total</small>
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
              <h2>Every frozen boundary reconciled.</h2>
            </div>
            <div className="quality-badge"><i /> 0 duplicate event IDs</div>
          </div>
          <div className="quality-summary">
            <div><strong>145</strong><span>frozen source files</span></div>
            <div><strong>0</strong><span>prefix hash mismatches</span></div>
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
          <p>Aggregate snapshot generated {generatedDate} UTC</p>
        </div>
      </footer>
    </main>
  );
}
