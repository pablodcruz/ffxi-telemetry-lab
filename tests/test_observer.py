from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ffxi_telemetry.observer import sample_state


def test_observer_tolerates_missing_and_samples_state(tmp_path: Path):
    source_root = tmp_path / "source"
    data_dir = tmp_path / "data"
    source_root.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(source_root)], check=True, capture_output=True)
    assert sample_state(source_root, data_dir) is None

    state_path = source_root / "runtime/farm-supervisor/primary.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "agent_id": "primary",
                "lease_id": "lease-1",
                "phase": "engaged",
                "active_zone_id": 100,
                "current_target": {"name": "Synthetic"},
                "config": {"maximum_fights": 10},
                "counters": {"fights_completed": 1, "exp_earned": 50},
                "metrics": {"maximum_handoff_queue_ms": 10},
            }
        ),
        encoding="utf-8",
    )
    result = sample_state(source_root, data_dir)
    assert result is not None
    assert result["written_rows"] == 1
    assert list((data_dir / "bronze/source=state_snapshot").rglob("*.parquet"))
