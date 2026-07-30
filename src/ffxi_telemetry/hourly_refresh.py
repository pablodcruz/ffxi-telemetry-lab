from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, Optional

from .blob_publish import publish_public_snapshot
from .collector import collect
from .observer import sample_state
from .public_export import export_public_snapshot
from .warehouse import prepare_warehouse


@contextmanager
def _refresh_lock(data_dir: Path) -> Iterator[None]:
    lock_path = data_dir / ".state" / "public-refresh.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another public refresh is already running") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _dbt_binary(explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    configured = os.getenv("TELEMETRY_DBT_BIN")
    if configured:
        return configured
    adjacent = Path(sys.executable).with_name("dbt")
    if adjacent.is_file():
        return str(adjacent)
    discovered = shutil.which("dbt")
    if discovered:
        return discovered
    raise RuntimeError("dbt executable not found; set TELEMETRY_DBT_BIN")


def _build_gold_models(
    project_dir: Path,
    data_dir: Path,
    duckdb_path: Path,
    dbt_bin: Optional[str] = None,
) -> None:
    log_dir = data_dir / "logs" / "dbt"
    target_dir = data_dir / ".state" / "dbt-target"
    log_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)
    environment = {
        **os.environ,
        "TELEMETRY_DUCKDB_PATH": str(duckdb_path),
    }
    completed = subprocess.run(
        [
            _dbt_binary(dbt_bin),
            "--log-path",
            str(log_dir),
            "build",
            "--profiles-dir",
            str(project_dir),
            "--target-path",
            str(target_dir),
        ],
        cwd=project_dir,
        env=environment,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout)[-4000:]
        raise RuntimeError(f"dbt build failed:\n{details}")


def refresh_public_metrics(
    source_root: Path,
    data_dir: Path,
    duckdb_path: Path,
    output: Path,
    *,
    upload: bool = True,
    blob_pathname: str = "telemetry/latest.json",
    project_dir: Optional[Path] = None,
    dbt_bin: Optional[str] = None,
) -> Dict[str, object]:
    resolved_project = project_dir or Path(__file__).resolve().parents[2]
    with _refresh_lock(data_dir):
        collection = collect(
            source_root,
            data_dir,
            historical=False,
            full_scan=False,
        )
        observation = sample_state(source_root, data_dir)
        warehouse = prepare_warehouse(data_dir, duckdb_path)
        _build_gold_models(
            resolved_project,
            data_dir,
            duckdb_path,
            dbt_bin,
        )
        exported = export_public_snapshot(duckdb_path, str(output))
        published = (
            publish_public_snapshot(output, pathname=blob_pathname)
            if upload
            else None
        )
    return {
        "collection": collection,
        "observation": observation,
        "warehouse": warehouse,
        "export": exported,
        "publish": published,
    }
