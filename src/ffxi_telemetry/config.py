from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_local_path(value: Optional[str], default: Path) -> Path:
    path = Path(value).expanduser() if value else default
    return path.resolve()


@dataclass(frozen=True)
class Settings:
    source_root: Optional[Path]
    data_dir: Path
    duckdb_path: Path
    observer_interval_seconds: float

    @classmethod
    def from_env(
        cls,
        source_root: Optional[str] = None,
        data_dir: Optional[str] = None,
        duckdb_path: Optional[str] = None,
        observer_interval_seconds: Optional[float] = None,
    ) -> "Settings":
        repo = repository_root()
        raw_source = source_root or os.getenv("FFXI_SOURCE_ROOT")
        resolved_source = Path(raw_source).expanduser().resolve() if raw_source else None
        resolved_data = _resolve_local_path(
            data_dir or os.getenv("TELEMETRY_DATA_DIR"),
            repo / "data",
        )
        resolved_duckdb = _resolve_local_path(
            duckdb_path or os.getenv("TELEMETRY_DUCKDB_PATH"),
            resolved_data / "warehouse" / "telemetry.duckdb",
        )
        raw_interval = (
            observer_interval_seconds
            if observer_interval_seconds is not None
            else float(os.getenv("TELEMETRY_OBSERVER_INTERVAL_SECONDS", "3"))
        )
        if not 2 <= raw_interval <= 5:
            raise ValueError("observer interval must be between 2 and 5 seconds")
        return cls(
            source_root=resolved_source,
            data_dir=resolved_data,
            duckdb_path=resolved_duckdb,
            observer_interval_seconds=float(raw_interval),
        )

    def require_source_root(self) -> Path:
        if self.source_root is None:
            raise ValueError("source root is required via --source-root or FFXI_SOURCE_ROOT")
        if not self.source_root.is_dir():
            raise ValueError(f"source root is not a directory: {self.source_root}")
        return self.source_root
