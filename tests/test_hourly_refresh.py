from pathlib import Path

import pytest

from ffxi_telemetry import hourly_refresh
from ffxi_telemetry.blob_publish import validate_public_snapshot
from ffxi_telemetry.config import Settings


def test_hourly_refresh_runs_isolated_pipeline_without_upload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[str] = []
    source_root = tmp_path / "source"
    data_dir = tmp_path / "data"
    duckdb_path = data_dir / "warehouse/telemetry.duckdb"
    output = data_dir / "public/latest.json"
    source_root.mkdir()

    monkeypatch.setattr(
        hourly_refresh,
        "collect",
        lambda *args, **kwargs: calls.append("collect") or {"written_rows": 2},
    )
    monkeypatch.setattr(
        hourly_refresh,
        "sample_state",
        lambda *args, **kwargs: calls.append("observe") or {"written_rows": 1},
    )
    monkeypatch.setattr(
        hourly_refresh,
        "prepare_warehouse",
        lambda *args, **kwargs: calls.append("warehouse") or {"bronze_rows": 3},
    )
    monkeypatch.setattr(
        hourly_refresh,
        "_build_gold_models",
        lambda *args, **kwargs: calls.append("dbt"),
    )
    monkeypatch.setattr(
        hourly_refresh,
        "export_public_snapshot",
        lambda *args, **kwargs: calls.append("export")
        or {"generated_at": "2026-07-30T20:05:00+00:00"},
    )

    result = hourly_refresh.refresh_public_metrics(
        source_root,
        data_dir,
        duckdb_path,
        output,
        upload=False,
        project_dir=tmp_path,
    )

    assert calls == ["collect", "observe", "warehouse", "dbt", "export"]
    assert result["publish"] is None
    assert (data_dir / ".state/public-refresh.lock").is_file()


def test_public_snapshot_privacy_guard_rejects_row_identifiers() -> None:
    snapshot = {
        "privacy": {
            "classification": "public_aggregate",
            "contains_raw_payloads": False,
            "contains_agent_ids": False,
            "contains_lease_ids": False,
        },
        "datasets": {"unsafe": [{"lease_id": "private"}]},
    }

    with pytest.raises(ValueError, match="forbidden public snapshot field"):
        validate_public_snapshot(snapshot)


def test_one_minute_observer_cadence_is_valid(tmp_path: Path) -> None:
    settings = Settings.from_env(
        source_root=str(tmp_path),
        data_dir=str(tmp_path / "data"),
        observer_interval_seconds=60,
    )

    assert settings.observer_interval_seconds == 60
