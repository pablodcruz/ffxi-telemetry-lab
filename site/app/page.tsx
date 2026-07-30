const dailyFights = [
  { day: "Jul 28", value: 68 },
  { day: "Jul 29", value: 707 },
  { day: "Jul 30", value: 470 },
];

const combatDays = [
  { day: "Jul 28", rate: 30.2, fights: 68 },
  { day: "Jul 29", rate: 22.6, fights: 707 },
  { day: "Jul 30", rate: 21.7, fights: 470 },
];

const operations = [
  { name: "enable_control", count: 12219, success: "99.88%" },
  { name: "gameplay_command", count: 7962, success: "97.94%" },
  { name: "target_entity", count: 5422, success: "96.85%" },
  { name: "clear_target", count: 5096, success: "100%" },
  { name: "emergency_stop", count: 3650, success: "99.62%" },
];

const qualityRows = [
  { source: "Agent actions", rows: "47,094", malformed: 0, status: "Reconciled" },
  { source: "Supervisor events", rows: "29,858", malformed: 0, status: "Reconciled" },
  { source: "Navigation probes", rows: "138", malformed: 0, status: "Reconciled" },
  { source: "State snapshots", rows: "1", malformed: 0, status: "Observed" },
];

function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <article className="metric">
      <p>{label}</p>
      <strong>{value}</strong>
      <span>{note}</span>
    </article>
  );
}

export default function Home() {
  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="FFXI Telemetry home">
          <span className="brand-mark">XI</span>
          <span>FFXI Telemetry</span>
        </a>
        <nav aria-label="Dashboard sections">
          <a href="#progression">Progression</a>
          <a href="#combat">Combat</a>
          <a href="#navigation">Navigation</a>
          <a href="#quality">Data quality</a>
        </nav>
        <span className="live-badge">Aggregate snapshot</span>
      </header>

      <section className="hero" id="top">
        <div className="eyebrow">FFXI Agent Lab · July 25–30, 2026</div>
        <h1>Autonomy, measured.</h1>
        <p className="lede">
          A public view of progression, combat reliability, navigation, and MCP
          control—built from an independent, read-only analytics pipeline.
        </p>
        <div className="privacy-line">
          <span className="privacy-dot" />
          No raw payloads, agent IDs, lease IDs, or full Git SHAs are published.
        </div>
      </section>

      <section className="metric-grid" aria-label="Headline telemetry metrics">
        <Metric label="Completed fights" value="1,245" note="Authoritative events" />
        <Metric label="MCP operations" value="47,094" note="98.35% successful" />
        <Metric label="Probe arrival rate" value="55.1%" note="76 of 138 attempts" />
        <Metric label="Malformed rows" value="0" note="At frozen backfill boundary" />
      </section>

      <section className="panel progression" id="progression">
        <div className="section-heading">
          <div>
            <span className="kicker">Autonomous progression</span>
            <h2>1,245 fights across three active days</h2>
          </div>
          <div className="section-stat">
            <strong>10</strong>
            <span>level + objective milestones</span>
          </div>
        </div>
        <div className="chart-card">
          <div className="chart-header">
            <div>
              <h3>Completed fights by day</h3>
              <p>Count of `fight_complete` events</p>
            </div>
            <span className="source-tag">Gold · progression</span>
          </div>
          <div className="column-chart" role="img" aria-label="Completed fights by day">
            {dailyFights.map((point) => (
              <div className="column-item" key={point.day}>
                <strong>{point.value}</strong>
                <div className="column-track">
                  <div
                    className="column-fill"
                    style={{ height: `${Math.max(10, (point.value / 707) * 100)}%` }}
                  />
                </div>
                <span>{point.day}</span>
              </div>
            ))}
          </div>
        </div>
        <aside className="coverage-callout">
          <strong>Coverage note</strong>
          <p>
            Historical fight events do not contain EXP deltas. The first
            read-only state observation recorded an in-lease EXP counter of
            21,838; it is not presented as a historical total.
          </p>
        </aside>
      </section>

      <section className="split-section" id="combat">
        <article className="panel">
          <div className="section-heading compact">
            <div>
              <span className="kicker">Combat reliability</span>
              <h2>Attack rejection eased over the window</h2>
            </div>
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
              <h2>Combat capabilities observed</h2>
            </div>
          </div>
          <div className="action-total"><strong>1,037</strong><span>combat actions</span></div>
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
        <article className="panel">
          <div className="section-heading compact">
            <div>
              <span className="kicker">Navigation</span>
              <h2>Probe outcomes are mixed, not binary</h2>
            </div>
          </div>
          <div className="outcome-bar" aria-label="Collision probe outcomes">
            <div className="arrived" style={{ width: "55.1%" }}>76</div>
            <div className="partial" style={{ width: "30.4%" }}>42</div>
            <div className="stalled" style={{ width: "14.5%" }}>20</div>
          </div>
          <ul className="legend outcome-legend">
            <li><span className="dot arrived" /> Arrived <strong>55.1%</strong></li>
            <li><span className="dot partial" /> Partial progress <strong>30.4%</strong></li>
            <li><span className="dot stalled" /> Stalled <strong>14.5%</strong></li>
          </ul>
        </article>

        <article className="panel">
          <div className="section-heading compact">
            <div>
              <span className="kicker">Mobility signals</span>
              <h2>World movement activity</h2>
            </div>
          </div>
          <div className="signal-grid">
            <div><strong>275</strong><span>Camp relocations</span></div>
            <div><strong>10</strong><span>Zone transitions</span></div>
            <div><strong>89</strong><span>Line-of-sight nudges</span></div>
            <div><strong>964</strong><span>Teleport operations*</span></div>
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
            <span className="kicker">MCP operation reliability</span>
            <h2>The control plane is broadly reliable</h2>
          </div>
          <div className="section-stat"><strong>778</strong><span>failed operations</span></div>
        </div>
        <div className="operation-table" role="table" aria-label="Top MCP operations">
          <div className="operation-head" role="row">
            <span>Operation</span><span>Volume</span><span>Success</span>
          </div>
          {operations.map((operation) => (
            <div className="operation-row" role="row" key={operation.name}>
              <code>{operation.name}</code>
              <span>{operation.count.toLocaleString()}</span>
              <strong>{operation.success}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="panel quality-panel" id="quality">
        <div className="section-heading">
          <div>
            <span className="kicker">Data quality</span>
            <h2>Every frozen source boundary reconciled</h2>
          </div>
          <div className="quality-badge">0 duplicate event IDs</div>
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
        <span className="kicker">How to read this dashboard</span>
        <h2>Observable facts first. Inference always labeled.</h2>
        <div className="method-grid">
          <p><strong>Immutable Bronze.</strong> Valid input lines retain their complete raw payload locally.</p>
          <p><strong>Tested Gold.</strong> Cards and charts trace to dbt models with uniqueness and reconciliation tests.</p>
          <p><strong>Git caveat.</strong> Historical commit attribution is inferred from commit time, never presented as authoritative.</p>
        </div>
      </section>

      <footer>
        <div>
          <strong>FFXI Telemetry</strong>
          <span>Independent from gameplay by design.</span>
        </div>
        <p>Aggregate snapshot generated Jul 30, 2026 · 16:18 UTC</p>
      </footer>
    </main>
  );
}
