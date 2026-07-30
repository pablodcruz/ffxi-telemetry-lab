from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pyarrow.parquet as pq

from ffxi_telemetry.collector import collect


def _write_source_fixture(root: Path) -> None:
    (root / "runtime/audit").mkdir(parents=True)
    (root / "runtime/farm-supervisor").mkdir(parents=True)
    (root / "runtime/navigation").mkdir(parents=True)
    (root / "runtime/audit/agent-actions.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-07-30T00:00:00Z",
                "agent_id": "primary",
                "operation": "gameplay_command",
                "outcome": "ok",
                "duration_ms": 10,
                "params": {},
            }
        )
        + "\n"
        + "{malformed\n",
        encoding="utf-8",
    )
    (root / "runtime/farm-supervisor/lease.log").write_text(
        json.dumps(
            {
                "at": "2026-07-30T00:00:01Z",
                "event": "fight_complete",
                "lease_id": "lease-1",
                "fight": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "runtime/navigation/collision-probes.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-07-30T00:00:02Z",
                "agent_id": "primary",
                "outcome": "clear",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "tests@example.invalid"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Tests"], check=True)
    marker = root / "README.md"
    marker.write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "commit",
            "-m",
            "fixture",
            "--date",
            "2026-07-29T00:00:00Z",
        ],
        check=True,
        capture_output=True,
        env={
            **__import__("os").environ,
            "GIT_COMMITTER_DATE": "2026-07-29T00:00:00Z",
        },
    )


def _allowed_hashes(root: Path) -> dict[str, str]:
    paths = [
        root / "runtime/audit/agent-actions.jsonl",
        root / "runtime/farm-supervisor/lease.log",
        root / "runtime/navigation/collision-probes.jsonl",
    ]
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_backfill_reconciles_quarantines_and_is_idempotent(tmp_path: Path):
    source_root = tmp_path / "source"
    data_dir = tmp_path / "telemetry-data"
    source_root.mkdir()
    _write_source_fixture(source_root)
    before = _allowed_hashes(source_root)

    first = collect(source_root, data_dir, historical=True, full_scan=True)
    assert first["reconciled"] is True
    assert first["written_rows"] == 3
    assert first["quarantined_rows"] == 1
    assert sum(item["valid_json_rows"] for item in first["sources"].values()) == 3
    assert sum(item["malformed_rows"] for item in first["sources"].values()) == 1

    second = collect(source_root, data_dir, historical=True, full_scan=True)
    assert second["reconciled"] is True
    assert second["written_rows"] == 0
    assert second["quarantined_rows"] == 1
    assert sum(item["duplicate_rows"] for item in second["sources"].values()) == 3

    parquet_files = list((data_dir / "bronze").rglob("*.parquet"))
    rows = sum(pq.ParquetFile(path).metadata.num_rows for path in parquet_files)
    assert rows == 3
    assert _allowed_hashes(source_root) == before
    assert len(list((data_dir / "quarantine").glob("*.jsonl"))) == 2
