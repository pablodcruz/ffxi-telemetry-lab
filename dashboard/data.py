from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = REPOSITORY_ROOT / "data" / "warehouse" / "telemetry.duckdb"
DEFAULT_PUBLIC_SNAPSHOT = REPOSITORY_ROOT / "dashboard" / "public_snapshot.json"


def load_dashboard_snapshot() -> Dict[str, object]:
    database = Path(os.getenv("TELEMETRY_DUCKDB_PATH", DEFAULT_DATABASE)).expanduser()
    if database.is_file():
        from ffxi_telemetry.public_export import build_public_snapshot

        snapshot = build_public_snapshot(database.resolve())
        snapshot["mode"] = "local_gold_models"
        return snapshot
    public_path = Path(
        os.getenv("TELEMETRY_PUBLIC_SNAPSHOT", DEFAULT_PUBLIC_SNAPSHOT)
    ).expanduser()
    if not public_path.is_file():
        raise FileNotFoundError(
            "No local Gold database or reviewed public snapshot is available. "
            "Run the pipeline and `ffxi-telemetry export-public`."
        )
    with public_path.open(encoding="utf-8") as handle:
        snapshot = json.load(handle)
    snapshot["mode"] = "published_aggregate_snapshot"
    return snapshot
