from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import duckdb
import pyarrow as pa

EMPTY_BRONZE_SQL = """
select
  cast(null as varchar) as event_id,
  cast(null as timestamptz) as event_time,
  cast(null as timestamptz) as ingested_at,
  cast(null as varchar) as source,
  cast(null as varchar) as source_file,
  cast(null as bigint) as source_line_number,
  cast(null as varchar) as event_type,
  cast(null as integer) as schema_version,
  cast(null as varchar) as agent_id,
  cast(null as varchar) as lease_id,
  cast(null as varchar) as source_git_sha,
  cast(null as varchar) as git_sha_provenance,
  cast(null as varchar) as source_fingerprint_sha256,
  cast(null as varchar) as collector_session_id,
  cast(null as varchar) as raw_json
where false
"""


def _manifest_rows(data_dir: Path) -> tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    session_rows: List[Dict[str, object]] = []
    source_rows: List[Dict[str, object]] = []
    manifest_dir = data_dir / ".state" / "manifests"
    if not manifest_dir.exists():
        return session_rows, source_rows
    for path in sorted(manifest_dir.glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            manifest = json.load(handle)
        session_rows.append(
            {
                "session_id": manifest.get("session_id"),
                "started_at": manifest.get("started_at"),
                "completed_at": manifest.get("completed_at"),
                "mode": manifest.get("mode"),
                "full_scan": manifest.get("full_scan"),
                "written_rows": manifest.get("written_rows", 0),
                "quarantined_rows": manifest.get("quarantined_rows", 0),
                "reconciled": manifest.get("reconciled", False),
            }
        )
        for source, stats in manifest.get("sources", {}).items():
            source_rows.append(
                {
                    "session_id": manifest.get("session_id"),
                    "source": source,
                    **stats,
                }
            )
    return session_rows, source_rows


def _replace_table_from_rows(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    rows: List[Dict[str, object]],
    empty_sql: str,
) -> None:
    if rows:
        relation = pa.Table.from_pylist(rows)
        connection.register("_incoming_rows", relation)
        connection.execute(f"create or replace table {table_name} as select * from _incoming_rows")
        connection.unregister("_incoming_rows")
    else:
        connection.execute(f"create or replace table {table_name} as {empty_sql}")


def prepare_warehouse(data_dir: Path, duckdb_path: Path) -> Dict[str, int]:
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    parquet_paths = sorted((data_dir / "bronze").rglob("*.parquet"))
    connection = duckdb.connect(str(duckdb_path))
    try:
        if parquet_paths:
            escaped = [str(path).replace("'", "''") for path in parquet_paths]
            path_list = ", ".join(f"'{path}'" for path in escaped)
            connection.execute(
                "create or replace view bronze_events as "
                f"select * from read_parquet([{path_list}], union_by_name=true)"
            )
        else:
            connection.execute(f"create or replace view bronze_events as {EMPTY_BRONZE_SQL}")

        sessions, source_rows = _manifest_rows(data_dir)
        _replace_table_from_rows(
            connection,
            "ingestion_sessions",
            sessions,
            """
            select
              cast(null as varchar) session_id,
              cast(null as varchar) started_at,
              cast(null as varchar) completed_at,
              cast(null as varchar) mode,
              cast(null as boolean) full_scan,
              cast(null as bigint) written_rows,
              cast(null as bigint) quarantined_rows,
              cast(null as boolean) reconciled
            where false
            """,
        )
        _replace_table_from_rows(
            connection,
            "ingestion_source_reconciliation",
            source_rows,
            """
            select
              cast(null as varchar) session_id,
              cast(null as varchar) source,
              cast(null as bigint) files,
              cast(null as bigint) snapshot_bytes,
              cast(null as bigint) lines_read,
              cast(null as bigint) valid_json_rows,
              cast(null as bigint) malformed_rows,
              cast(null as bigint) new_rows,
              cast(null as bigint) duplicate_rows
            where false
            """,
        )
        bronze_count = connection.execute("select count(*) from bronze_events").fetchone()[0]
        return {
            "bronze_rows": int(bronze_count),
            "ingestion_sessions": len(sessions),
            "source_reconciliation_rows": len(source_rows),
        }
    finally:
        connection.close()
