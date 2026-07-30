# FFXI Telemetry Lab execution plan

Recorded on 2026-07-30 in `America/New_York`.

## Read-only source inventory

The source repository was inspected without reading any prohibited credential or
backup path.

- Source repository: `/Users/a123/Documents/FFXI Agents Server`
- Branch: `codex/unified-farm-supervisor`
- HEAD: `3333af7f924f5bbb387953a6ef45de910787d493`
- Agent actions at inspection: 46,659 valid JSON records, 0 malformed
- Farm supervisor logs at inspection: 29,616 valid JSON records across 143
  lease files, 0 malformed
- Navigation probes at inspection: 138 valid JSON records, 0 malformed
- Total inspected event records: 76,413

The gameplay process remained active, so these are inspection-time counts, not
hardcoded ingestion expectations. Every collector run freezes the byte length
and fingerprint of each allowed file before reading it. Its manifest is the
authoritative start-of-run reconciliation boundary.

Historical `fight_complete` records do not contain EXP deltas, deaths, or
recoveries. Those counters are present in the mutable supervisor state and will
only be reported for observer-covered periods. Historical EXP will remain
unavailable instead of being manufactured.

## Phased execution

1. Scaffold an independent repository with private-by-default ignores and no
   runtime dependency from gameplay to analytics.
2. Implement allowlisted, read-only JSONL sources and an immutable Parquet sink
   behind source/sink interfaces. Freeze live-file boundaries, generate
   deterministic IDs, infer historical Git attribution, quarantine malformed
   rows, persist offsets locally, and reconcile every run.
3. Create DuckDB views and dbt Silver/Gold models with uniqueness, completeness,
   accepted-value, relationship, duplicate, quarantine, and count tests.
4. Add a reproducible notebook and a Streamlit/Plotly dashboard that query Gold
   models only. Display coverage and inference labels beside affected metrics.
5. Add a 2–5 second, change-aware, read-only state observer that tolerates
   missing, replaced, partial, or offline source files.
6. Add an opt-in, allowlisted MariaDB snapshot command that requires a dedicated
   read-only account and lands snapshots only in local Bronze Parquet.
7. Publish only reviewed aggregate data. Keep raw telemetry, databases,
   Parquet, state, executed notebooks, and secrets ignored. Evaluate Kafka,
   Redpanda, or ClickHouse only after measured limitations.

## Safety invariants

- Only the three allowlisted event paths and the single observer state file are
  readable by application code.
- Collection never opens source files for writing and never asks gameplay to
  call, wait for, or depend on analytics.
- Collector state, quarantine, Parquet, DuckDB, and snapshots live only in this
  repository's ignored local data directory.
- Public exports contain aggregate Gold metrics only and require an explicit
  export command.
