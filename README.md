# FFXI Telemetry Lab

[Open the public FFXI Telemetry dashboard](https://ffxi-telemetry.vercel.app)

Local-first data engineering and analytics for telemetry emitted by FFXI Agent
Lab. This repository is operationally independent from gameplay: it only reads
append-only files and optional database snapshots. Gameplay never imports,
calls, waits for, or depends on this project.

The public dashboard is a reviewed aggregate snapshot suitable for a README or
YouTube stream description. Raw payloads, agent IDs, lease IDs, targets, full
Git SHAs, credentials, Parquet, and DuckDB files are never published.

## Architecture

```text
FFXI JSONL files (read only)
Optional allowlisted NM map snapshot (read only)
  -> allowlisted collector
  -> immutable Bronze Parquet + quarantine
  -> DuckDB / dbt Silver
  -> tested Gold models
  -> notebook + local Streamlit dashboard
  -> reviewed aggregate export
  -> public dashboard
```

Backpressure ends at the source project's append-only files. Kafka, Redpanda,
ClickHouse, Airflow, Spark, and Kubernetes are deliberately absent from the
first milestone.

## Validated snapshot

The first authoritative backfill froze each live file at its start-of-run byte
boundary, then reconciled exactly:

| Source | Valid rows | Malformed |
| --- | ---: | ---: |
| MCP action audit | 52,575 | 0 |
| Farm supervisor events | 33,042 | 0 |
| Navigation probes | 138 | 0 |
| **Static total** | **85,755** | **0** |

All 157 frozen file prefixes reconciled to the valid records present at the
start of the run. Active logs appended after that boundary as expected; the
collector did not alter source bytes.

The gameplay source was observed on branch
`codex/unified-farm-supervisor` at
`650ae7c9c37aaceec773db0fada442e70e4219ef`. Historical event-to-commit
attribution is explicitly labeled `inferred_from_commit_time`; future sessions
record the source HEAD as `observed_at_ingestion`.

## Quick start

Requires Python 3.9 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Set `FFXI_SOURCE_ROOT` in the ignored `.env` file. The path is configuration,
not application code.

Run a full backfill and build the warehouse:

```bash
ffxi-telemetry backfill
ffxi-telemetry prepare-warehouse
dbt build --profiles-dir .
```

Run incremental collection with the same idempotent collector:

```bash
ffxi-telemetry collect
```

Offsets, fingerprints, manifests, quarantine records, Parquet, and DuckDB stay
under ignored local paths in this repository. Source files are opened read-only
and are never truncated, rotated, locked, renamed, or modified.

## Event contract and replay

Every valid Bronze row contains:

- `event_id`: SHA-256 of source-relative path, line number, and raw line
- `event_time` and `ingested_at`
- `source`, `source_file`, and `source_line_number`
- `event_type`, `schema_version`, `agent_id`, and `lease_id`
- `source_git_sha` and `git_sha_provenance`
- complete `raw_json`

Bronze is partitioned by `source` and `event_date`. Malformed lines are copied
to local quarantine with their bytes base64-encoded and are included in
reconciliation instead of being silently discarded. Deterministic IDs and a
local seen-ID index provide at-least-once ingestion without duplicate events.
The source and Parquet sink implement explicit interfaces so another sink can
be added without changing gameplay.

## Data models

Silver models normalize the heterogeneous event families while retaining
Bronze lineage:

- `silver_agent_actions`
- `silver_supervisor_events`
- `silver_leases`
- `silver_fights`
- `silver_navigation_attempts`
- `silver_state_snapshots`

Gold models power the notebook and dashboard:

- `gold_autonomous_progression`
- `gold_combat_reliability`
- `gold_navigation_performance`
- `gold_mcp_operation_reliability`
- `gold_performance_by_git_commit`
- `gold_data_quality`

Unavailable fields remain unavailable. Historical fight events do not contain
EXP deltas, deaths, recoveries, job, or trustworthy handoff duration. The
dashboard labels observer-only counters and proxy metrics rather than filling
those gaps.

## Notebook and dashboards

Execute the reproducible notebook from beginning to end:

```bash
python scripts/run_notebook.py
```

The executed copy is written to the ignored
`artifacts/notebooks/` directory. The tracked notebook contains code and
documentation but no embedded private rows.

Run the interactive local dashboard against the Gold database:

```bash
streamlit run dashboard/app.py
```

Create a reviewed, row-free public snapshot after a successful dbt build:

```bash
ffxi-telemetry export-public \
  --site-output site/public/data/public_snapshot.json
```

The static public dashboard source lives in `site/`. Its tracked site snapshot
is the same reviewed, aggregate-only export used by the local dashboard. Inspect
the generated snapshot and rerun the validation suite before publishing.

### Notorious monster watch

The public dashboard includes a horizontally scrollable carousel of 20 curated
lottery NMs. Each card uses a locally mirrored, attributed FFXIclopedia image
and a rule reference pinned to a reviewed LandSandBoat commit. The displayed
script chance and cooldown are reference defaults until a map observation
reports effective private-server values.

Current NM state is optional and hourly. Configure an ignored, read-only JSON
snapshot path when the private map observer is available:

```bash
TELEMETRY_NM_STATE_PATH=/private/path/to/nm-state.json
```

The public exporter accepts only the fields documented in
[`docs/nm_observer_contract.md`](docs/nm_observer_contract.md). Extra fields,
including raw payloads or identifiers, reject the export. Missing observations
and observations older than two hours are rendered as `Unknown`; the dashboard
never infers lottery eligibility from uptime alone.

## Continuous hourly public metrics

The optional observer samples only `runtime/farm-supervisor/primary.json` and
immediately records lease or phase changes it sees:

```bash
ffxi-telemetry observe
```

It uses stable double reads to tolerate partial atomic replacements, missing
files, restarts, and an offline source project. Snapshots include observation
time, lease, phase, zone, current target, counters, metrics, configuration hash,
and the source HEAD observed at ingestion. It writes only inside this project
and never polls gameplay MCP.

The live installation runs the independent publisher at five minutes past each
hour:

```bash
ffxi-telemetry refresh-public
```

That command incrementally collects the allowlisted append-only files, samples
current state, refreshes DuckDB, runs the tested dbt models, exports the reviewed
aggregate contract, and overwrites one public Vercel Blob JSON object. Raw
telemetry never leaves the local machine. A publishing failure cannot stop the
observer or gameplay.

After creating a public Blob store for the linked Vercel project, pull its
ignored environment values into `.env.vercel`. Schedule `refresh-public` with a
local task runner that can read the configured source root. The current
installation uses an active Codex hourly automation; this avoids macOS denying
an unattended LaunchAgent access to a source under `Documents`.

Each hourly refresh takes one state sample, which is sufficient for hour-over-
hour EXP and gil counter deltas while keeping local work small. The public
dashboard checks the reviewed aggregate object every ten minutes
and whenever its tab regains focus. Hour charts show completed buckets only;
the current partial period and data age are labeled separately. Full local
history is retained indefinitely. The public extract keeps the latest 90 days
of hourly buckets plus durable daily and weekly rollups.

The same hourly publication includes the 20-row NM watchlist. It remains
operational when the map observer is absent: reference artwork and rules still
load, while direct-state fields remain explicitly unknown.

## Read-only MariaDB snapshots

MariaDB is opt-in and remains downstream of the file pipeline. A database
administrator must create a dedicated account with `SELECT` only on the
required `xidb` tables; do not use the root account. Store its password only in
the ignored `.env` file or a system secret store.

Review the table allowlist and grain catalog in
`config/mariadb_tables.yml`, then run:

```bash
ffxi-telemetry snapshot-mariadb
```

The command rejects root-like usernames, starts a read-only transaction,
selects only cataloged tables, and lands immutable Bronze Parquet locally. It
does not create tables, views, triggers, or CDC in the operational database.

## Validation

```bash
pytest
ruff check src tests dashboard scripts
ffxi-telemetry prepare-warehouse
dbt build --profiles-dir .
python scripts/run_notebook.py
streamlit run dashboard/app.py
cd site && npm run build && npm test
```

The dbt suite checks event ID uniqueness/non-nullness, event-time completeness,
accepted outcomes, lease relationships, duplicate detection, quarantine
accounting, and exact source row reconciliation.

## Privacy and repository safety

Raw telemetry is private by default. `.gitignore` excludes:

- `.env` and credential/key material
- `data/`, quarantine, collector state, and logs
- JSONL, Parquet, DuckDB, and other database files
- executed notebooks and Jupyter state
- dbt outputs and Python/Node build artifacts

The collector uses an explicit source allowlist. It does not scan the source
repository and cannot ingest environment files, agent configuration, bridge
configuration, backups, cookies, tokens, stream keys, or database passwords.

Before publishing a public export, inspect the data-quality page and confirm
that it contains aggregates only. Never commit an executed notebook with
private rows.

## Scaling decisions

DuckDB remains the default engine until measured query latency, data volume,
refresh rate, or dashboard concurrency demonstrates a limit. Kafka or Redpanda
should be a separate milestone only when multiple independent consumers,
cross-machine streaming, CDC, or durable distributed offsets are actually
needed. Neither may become a gameplay runtime dependency.

The recorded source inventory and implementation plan are in
[`PLAN.md`](PLAN.md); dashboard metric definitions are in
[`docs/dashboard_contract.md`](docs/dashboard_contract.md).
