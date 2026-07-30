from __future__ import annotations

import base64
import json
import os
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

BRONZE_SCHEMA = pa.schema(
    [
        ("event_id", pa.string()),
        ("event_time", pa.timestamp("us", tz="UTC")),
        ("ingested_at", pa.timestamp("us", tz="UTC")),
        ("source", pa.string()),
        ("source_file", pa.string()),
        ("source_line_number", pa.int64()),
        ("event_type", pa.string()),
        ("schema_version", pa.int32()),
        ("agent_id", pa.string()),
        ("lease_id", pa.string()),
        ("source_git_sha", pa.string()),
        ("git_sha_provenance", pa.string()),
        ("source_fingerprint_sha256", pa.string()),
        ("collector_session_id", pa.string()),
        ("raw_json", pa.string()),
    ]
)


class ParquetBronzeSink:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.bronze_dir = data_dir / "bronze"
        self.quarantine_dir = data_dir / "quarantine"

    def existing_event_ids(self) -> set[str]:
        event_ids: set[str] = set()
        if not self.bronze_dir.exists():
            return event_ids
        for path in self.bronze_dir.rglob("*.parquet"):
            table = pq.ParquetFile(path).read(columns=["event_id"])
            event_ids.update(value for value in table["event_id"].to_pylist() if value)
        return event_ids

    @staticmethod
    def _partition_key(row: Dict[str, object]) -> Tuple[str, str]:
        event_time = row.get("event_time")
        event_date = event_time.date().isoformat() if event_time is not None else "unknown"
        return str(row["source"]), event_date

    def write_events(self, rows: List[Dict[str, object]], session_id: str) -> int:
        grouped: Dict[Tuple[str, str], List[Dict[str, object]]] = defaultdict(list)
        for row in rows:
            grouped[self._partition_key(row)].append(row)
        written = 0
        for (source, event_date), partition_rows in grouped.items():
            partition = self.bronze_dir / f"source={source}" / f"event_date={event_date}"
            partition.mkdir(parents=True, exist_ok=True)
            final_path = partition / f"{session_id}-{uuid.uuid4().hex[:12]}.parquet"
            temporary_path = partition / f".{final_path.name}.tmp"
            table = pa.Table.from_pylist(partition_rows, schema=BRONZE_SCHEMA)
            pq.write_table(table, temporary_path, compression="zstd")
            os.replace(temporary_path, final_path)
            written += len(partition_rows)
        return written

    def write_quarantine(self, rows: List[Dict[str, object]], session_id: str) -> int:
        if not rows:
            return 0
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        final_path = self.quarantine_dir / f"{session_id}.jsonl"
        temporary_path = self.quarantine_dir / f".{session_id}.tmp"
        with temporary_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                safe_row = dict(row)
                raw_line = safe_row.pop("raw_line")
                safe_row["raw_line_base64"] = base64.b64encode(raw_line).decode("ascii")
                handle.write(json.dumps(safe_row, sort_keys=True) + "\n")
        os.replace(temporary_path, final_path)
        return len(rows)
