from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .contracts import FrozenInput
from .git_provenance import CommitResolver, observed_head
from .identity import deterministic_event_id
from .sink import ParquetBronzeSink
from .source import AllowlistedJsonlSource
from .state import CollectorState


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_event_time(value: object) -> Optional[dt.datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _hash_file_prefix(path: Path, byte_limit: int) -> str:
    digest = hashlib.sha256()
    remaining = byte_limit
    with path.open("rb") as handle:
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest() if remaining == 0 else ""


def _resume_point(
    frozen: FrozenInput,
    saved: Dict[str, object],
    full_scan: bool,
) -> Tuple[int, int]:
    if full_scan or not saved:
        return 0, 0
    byte_offset = int(saved.get("byte_offset", 0))
    line_number = int(saved.get("line_number", 0))
    prefix_hash = str(saved.get("prefix_sha256", ""))
    if byte_offset > frozen.byte_limit:
        return 0, 0
    if not prefix_hash or _hash_file_prefix(frozen.path, byte_offset) != prefix_hash:
        return 0, 0
    return byte_offset, line_number


def collect(
    source_root: Path,
    data_dir: Path,
    historical: bool,
    full_scan: bool,
) -> Dict[str, object]:
    session_id = _utc_now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10]
    ingested_at = _utc_now()
    source = AllowlistedJsonlSource(source_root)
    frozen_inputs = source.freeze()
    sink = ParquetBronzeSink(data_dir)
    collector_state = CollectorState(data_dir)
    saved_offsets = collector_state.load()
    next_offsets = dict(saved_offsets)
    existing_ids = sink.existing_event_ids()
    seen_ids = set(existing_ids)
    resolver = CommitResolver.from_repository(source_root) if historical else None
    observed_sha = observed_head(source_root)

    event_rows: List[Dict[str, object]] = []
    quarantined_rows: List[Dict[str, object]] = []
    source_stats: Dict[str, Dict[str, object]] = defaultdict(
        lambda: {
            "files": 0,
            "snapshot_bytes": 0,
            "lines_read": 0,
            "valid_json_rows": 0,
            "malformed_rows": 0,
            "new_rows": 0,
            "duplicate_rows": 0,
        }
    )
    file_results: List[Dict[str, object]] = []

    for frozen in frozen_inputs:
        start_byte, start_line = _resume_point(
            frozen,
            saved_offsets.get(frozen.source_file, {}),
            full_scan,
        )
        stats = source_stats[frozen.source]
        stats["files"] += 1
        stats["snapshot_bytes"] += frozen.byte_limit
        file_line_count = 0
        file_valid = 0
        file_malformed = 0
        last_line_number = start_line
        for record in source.records(frozen, start_byte, start_line):
            file_line_count += 1
            last_line_number = record.source_line_number
            stats["lines_read"] += 1
            event_id = deterministic_event_id(
                frozen.source_file,
                record.source_line_number,
                record.raw_line,
            )
            try:
                raw_text = record.raw_line.decode("utf-8").rstrip("\r\n")
                payload = json.loads(raw_text)
                if not isinstance(payload, dict):
                    raise ValueError("JSON value is not an object")
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                file_malformed += 1
                stats["malformed_rows"] += 1
                quarantined_rows.append(
                    {
                        "event_id": event_id,
                        "source": frozen.source,
                        "source_file": frozen.source_file,
                        "source_line_number": record.source_line_number,
                        "error_type": type(exc).__name__,
                        "raw_line": record.raw_line,
                    }
                )
                continue

            file_valid += 1
            stats["valid_json_rows"] += 1
            if event_id in seen_ids:
                stats["duplicate_rows"] += 1
                continue

            event_time_text = payload.get(frozen.timestamp_field)
            event_time = _parse_event_time(event_time_text)
            event_type = (
                str(payload.get(frozen.event_type_field) or "unknown")
                if frozen.event_type_field
                else "navigation_probe"
            )
            if historical:
                git_sha = resolver.at_or_before(event_time_text) if resolver else None
                provenance = "inferred_from_commit_time" if git_sha else "unavailable"
            else:
                git_sha = observed_sha
                provenance = "observed_at_ingestion" if git_sha else "unavailable"
            event_rows.append(
                {
                    "event_id": event_id,
                    "event_time": event_time,
                    "ingested_at": ingested_at,
                    "source": frozen.source,
                    "source_file": frozen.source_file,
                    "source_line_number": record.source_line_number,
                    "event_type": event_type,
                    "schema_version": 1,
                    "agent_id": (
                        str(payload["agent_id"]) if payload.get("agent_id") is not None else None
                    ),
                    "lease_id": (
                        str(payload["lease_id"]) if payload.get("lease_id") is not None else None
                    ),
                    "source_git_sha": git_sha,
                    "git_sha_provenance": provenance,
                    "source_fingerprint_sha256": frozen.fingerprint_sha256,
                    "collector_session_id": session_id,
                    "raw_json": raw_text,
                }
            )
            seen_ids.add(event_id)
            stats["new_rows"] += 1

        next_offsets[frozen.source_file] = {
            "byte_offset": frozen.byte_limit,
            "line_number": last_line_number,
            "prefix_sha256": frozen.fingerprint_sha256,
            "source": frozen.source,
        }
        file_results.append(
            {
                "source": frozen.source,
                "source_file": frozen.source_file,
                "snapshot_bytes": frozen.byte_limit,
                "fingerprint_sha256": frozen.fingerprint_sha256,
                "start_byte": start_byte,
                "start_line_number": start_line,
                "lines_read": file_line_count,
                "valid_json_rows": file_valid,
                "malformed_rows": file_malformed,
            }
        )

    written = sink.write_events(event_rows, session_id)
    quarantined = sink.write_quarantine(quarantined_rows, session_id)
    if written != len(event_rows) or quarantined != len(quarantined_rows):
        raise RuntimeError("sink row count did not match collector row count")

    collector_state.save(next_offsets)
    manifest: Dict[str, object] = {
        "session_id": session_id,
        "started_at": ingested_at.isoformat(),
        "completed_at": _utc_now().isoformat(),
        "mode": "historical_backfill" if historical else "incremental_collection",
        "full_scan": full_scan,
        "source_git_sha_observed_at_start": observed_sha,
        "git_sha_provenance": (
            "inferred_from_commit_time" if historical else "observed_at_ingestion"
        ),
        "existing_event_ids_at_start": len(existing_ids),
        "written_rows": written,
        "quarantined_rows": quarantined,
        "sources": dict(source_stats),
        "files": file_results,
        "reconciled": all(
            int(stats["lines_read"])
            == int(stats["valid_json_rows"]) + int(stats["malformed_rows"])
            for stats in source_stats.values()
        ),
    }
    manifest_path = collector_state.save_manifest(session_id, manifest)
    manifest["manifest_path"] = str(manifest_path)
    return manifest
