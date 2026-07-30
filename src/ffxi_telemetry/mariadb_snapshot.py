from __future__ import annotations

import datetime as dt
import decimal
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

import pymysql

from .git_provenance import observed_head
from .identity import deterministic_event_id
from .sink import ParquetBronzeSink

TABLE_CATALOG: Mapping[str, Tuple[str, ...]] = {
    "chars": ("charid",),
    "char_jobs": ("charid",),
    "char_inventory": ("charid", "location", "slot"),
    "char_missions": ("charid",),
    "item_basic": ("itemid",),
    "zone_settings": ("zoneid",),
}


def _json_value(value: object) -> object:
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def _connect() -> pymysql.Connection:
    password = os.getenv("MARIADB_PASSWORD")
    if not password:
        raise ValueError("MARIADB_PASSWORD is required in an ignored environment file")
    user = os.getenv("MARIADB_USER")
    if not user or user.lower() == "root":
        raise ValueError("MARIADB_USER must be a dedicated non-root read-only account")
    return pymysql.connect(
        host=os.getenv("MARIADB_HOST", "127.0.0.1"),
        port=int(os.getenv("MARIADB_PORT", "3306")),
        user=user,
        password=password,
        database=os.getenv("MARIADB_DATABASE", "xidb"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        read_timeout=30,
        write_timeout=30,
    )


def snapshot_tables(
    source_root: Path,
    data_dir: Path,
    table_names: Sequence[str],
) -> Dict[str, object]:
    invalid = sorted(set(table_names) - set(TABLE_CATALOG))
    if invalid:
        raise ValueError(f"tables are not in the reviewed allowlist: {', '.join(invalid)}")
    snapshot_at = dt.datetime.now(dt.timezone.utc)
    snapshot_id = snapshot_at.strftime("%Y%m%dT%H%M%S%f")
    source_sha = observed_head(source_root)
    rows_by_table: Dict[str, List[Dict[str, object]]] = {}
    connection = _connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("set session transaction read only")
            cursor.execute("start transaction read only")
            for table_name in table_names:
                cursor.execute(f"select * from `{table_name}`")
                rows_by_table[table_name] = list(cursor.fetchall())
            connection.rollback()
    finally:
        connection.close()

    bronze_rows: List[Dict[str, object]] = []
    counts: Dict[str, int] = {}
    for table_name, source_rows in rows_by_table.items():
        primary_key = TABLE_CATALOG[table_name]
        counts[table_name] = len(source_rows)
        schema_fingerprint = hashlib.sha256(
            ",".join(sorted(source_rows[0].keys()) if source_rows else []).encode("utf-8")
        ).hexdigest()
        for row_number, row in enumerate(source_rows, start=1):
            safe_row = {key: _json_value(value) for key, value in row.items()}
            raw_json = json.dumps(safe_row, sort_keys=True, separators=(",", ":"))
            key_payload = {key: safe_row.get(key) for key in primary_key}
            identity_bytes = json.dumps(
                {
                    "snapshot_id": snapshot_id,
                    "table": table_name,
                    "primary_key": key_payload,
                    "row": safe_row,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            source_file = f"mariadb/xidb/{table_name}"
            bronze_rows.append(
                {
                    "event_id": deterministic_event_id(
                        source_file,
                        row_number,
                        identity_bytes,
                    ),
                    "event_time": snapshot_at,
                    "ingested_at": snapshot_at,
                    "source": f"mariadb_{table_name}",
                    "source_file": source_file,
                    "source_line_number": row_number,
                    "event_type": "database_snapshot",
                    "schema_version": 1,
                    "agent_id": None,
                    "lease_id": None,
                    "source_git_sha": source_sha,
                    "git_sha_provenance": (
                        "observed_at_ingestion" if source_sha else "unavailable"
                    ),
                    "source_fingerprint_sha256": schema_fingerprint,
                    "collector_session_id": f"mariadb-{snapshot_id}",
                    "raw_json": raw_json,
                }
            )
    sink = ParquetBronzeSink(data_dir)
    written = sink.write_events(bronze_rows, f"mariadb-{snapshot_id}")
    return {"snapshot_id": snapshot_id, "written_rows": written, "tables": counts}
