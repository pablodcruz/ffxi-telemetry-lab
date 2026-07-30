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
| MCP action audit | 47,094 | 0 |
| Farm supervisor events | 29,858 | 0 |
| Navigation probes | 138 | 0 |
| **Static total** | **77,090** | **0** |

One later state-observer row was added separately, for 77,091 Bronze rows in the
validated warehouse. All 145 frozen file prefixes retained their original
hashes; two active logs appended after the boundary as expected. The collector
did not alter source bytes.

The gameplay source was observed on branch
`codex/unified-farm-supervisor` at
`3333af7f924f5bbb387953a6ef45de910787d493`. Historical event-to-commit
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
ffxi-telemetry export-public
```

The static public dashboard source lives in `site/`. Update its reviewed
aggregate constants only after inspecting the exported snapshot and rerunning
the validation suite.

## Low-frequency state observer

The observer samples only `runtime/farm-supervisor/primary.json`, every 2–5
seconds and on important changes:

```bash
ffxi-telemetry observe
```

It uses stable double reads to tolerate partial atomic replacements, missing
files, restarts, and an offline source project. Snapshots include observation
time, lease, phase, zone, current target, counters, metrics, configuration hash,
and the source HEAD observed at ingestion. It writes only inside this project
and never polls gameplay MCP.

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
