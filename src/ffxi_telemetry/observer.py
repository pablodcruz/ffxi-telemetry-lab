from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Optional

from .git_provenance import observed_head
from .identity import deterministic_event_id
from .sink import ParquetBronzeSink

STATE_RELATIVE_PATH = "runtime/farm-supervisor/primary.json"
MAX_STATE_BYTES = 1024 * 1024


def _read_stable_json(path: Path) -> Optional[Dict[str, object]]:
    try:
        before = path.stat()
        if before.st_size <= 0 or before.st_size > MAX_STATE_BYTES or path.is_symlink():
            return None
        raw = path.read_bytes()
        after = path.stat()
    except (FileNotFoundError, PermissionError, OSError):
        return None
    if (
        before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(raw) != before.st_size
    ):
        return None
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _configuration_hash(payload: Dict[str, object]) -> str:
    configuration = payload.get("config")
    canonical = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_state_row(source_root: Path) -> Optional[Dict[str, object]]:
    state_path = source_root / STATE_RELATIVE_PATH
    payload = _read_stable_json(state_path)
    if payload is None:
        return None

    observed_at = dt.datetime.now(dt.timezone.utc)
    observed_sha = observed_head(source_root)
    enriched = dict(payload)
    enriched["observation_time"] = observed_at.isoformat()
    enriched["configuration_hash"] = _configuration_hash(payload)
    enriched["observed_source_git_sha"] = observed_sha
    canonical = json.dumps(enriched, sort_keys=True, separators=(",", ":"))
    raw_bytes = canonical.encode("utf-8")
    observation_number = int(observed_at.timestamp() * 1_000_000)
    event_id = deterministic_event_id(
        STATE_RELATIVE_PATH,
        observation_number,
        raw_bytes,
    )
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    row = {
        "event_id": event_id,
        "event_time": observed_at,
        "ingested_at": observed_at,
        "source": "state_snapshot",
        "source_file": STATE_RELATIVE_PATH,
        "source_line_number": observation_number,
        "event_type": "state_snapshot",
        "schema_version": 1,
        "agent_id": str(payload["agent_id"]) if payload.get("agent_id") is not None else None,
        "lease_id": str(payload["lease_id"]) if payload.get("lease_id") is not None else None,
        "source_git_sha": observed_sha,
        "git_sha_provenance": "observed_at_ingestion" if observed_sha else "unavailable",
        "source_fingerprint_sha256": fingerprint,
        "collector_session_id": f"observer-{observed_at.strftime('%Y%m%d')}",
        "raw_json": canonical,
    }
    return row


def sample_state(source_root: Path, data_dir: Path) -> Optional[Dict[str, object]]:
    row = _build_state_row(source_root)
    if row is None:
        return None
    sink = ParquetBronzeSink(data_dir)
    written = sink.write_events(
        [row],
        f"observer-{row['event_time'].strftime('%Y%m%dT%H%M%S')}",
    )
    return {
        "written_rows": written,
        "event_id": row["event_id"],
        "observation_time": row["event_time"].isoformat(),
        "lease_id": row["lease_id"],
        "phase": json.loads(row["raw_json"]).get("phase"),
    }


def observe_forever(source_root: Path, data_dir: Path, interval_seconds: float) -> None:
    if not 2 <= interval_seconds <= 5:
        raise ValueError("observer interval must be between 2 and 5 seconds")
    last_important_state: Optional[tuple[object, ...]] = None
    pending_rows: list[Dict[str, object]] = []
    sink = ParquetBronzeSink(data_dir)
    try:
        while True:
            row = _build_state_row(source_root)
            if row is not None:
                pending_rows.append(row)
                payload = json.loads(row["raw_json"])
                important_state = (row.get("lease_id"), payload.get("phase"))
                state_changed = important_state != last_important_state
                if state_changed or len(pending_rows) >= 20:
                    sink.write_events(
                        pending_rows,
                        f"observer-{row['event_time'].strftime('%Y%m%dT%H%M%S')}",
                    )
                    pending_rows = []
                    last_important_state = important_state
            time.sleep(interval_seconds)
    finally:
        if pending_rows:
            latest = pending_rows[-1]["event_time"]
            sink.write_events(
                pending_rows,
                f"observer-{latest.strftime('%Y%m%dT%H%M%S')}",
            )
