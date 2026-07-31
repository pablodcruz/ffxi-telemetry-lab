from pathlib import Path

from ffxi_telemetry import public_export


def test_public_export_writes_identical_dashboard_and_site_snapshots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    snapshot = {
        "schema_version": 3,
        "generated_at": "2026-07-30T19:17:52+00:00",
        "datasets": {"progression_velocity": [{"period_grain": "hour"}]},
    }
    monkeypatch.setattr(public_export, "build_public_snapshot", lambda _: snapshot)
    dashboard_output = tmp_path / "dashboard.json"
    site_output = tmp_path / "site.json"

    result = public_export.export_public_snapshot(
        tmp_path / "telemetry.duckdb",
        str(dashboard_output),
        str(site_output),
    )

    assert dashboard_output.read_bytes() == site_output.read_bytes()
    assert result["datasets"] == {"progression_velocity": 1}
    assert result["site_output"] == str(site_output)
