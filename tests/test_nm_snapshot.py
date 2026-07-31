import datetime as dt
import json
from pathlib import Path

import pytest

from ffxi_telemetry.nm_snapshot import build_public_nm_datasets

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_catalog_exports_exactly_twenty_unknown_nms_without_observer() -> None:
    datasets = build_public_nm_datasets(project_root=PROJECT_ROOT)

    assert datasets["nm_observer"] == [
        {
            "observer_status": "not_configured",
            "observed_at": None,
            "map_started_at": None,
            "ruleset_git_sha": None,
            "tracked_nm_count": 20,
            "observed_nm_count": 0,
            "refresh_cadence": "hourly",
        }
    ]
    assert len(datasets["nm_status"]) == 20
    assert len({row["nm_key"] for row in datasets["nm_status"]}) == 20
    assert {row["status"] for row in datasets["nm_status"]} == {"unknown"}
    assert all(row["image_url"].startswith("/nm/") for row in datasets["nm_status"])
    assert all(row["recorded_defeat_count"] == 0 for row in datasets["nm_status"])


def test_recorded_defeats_enrich_history_without_inferring_status() -> None:
    datasets = build_public_nm_datasets(
        project_root=PROJECT_ROOT,
        recorded_defeats=[
            {
                "target_name": "Leaping Lizzy",
                "recorded_defeat_count": 4,
                "last_recorded_defeat_at": "2026-07-31 09:49:07.663-04",
            }
        ],
    )

    lizzy = next(
        row for row in datasets["nm_status"] if row["nm_key"] == "leaping-lizzy"
    )
    assert lizzy["recorded_defeat_count"] == 4
    assert lizzy["last_observed_kill_at"] == "2026-07-31T13:49:07.663000+00:00"
    assert lizzy["status"] == "unknown"
    assert lizzy["data_quality"] == "recorded_defeat_only"
    assert datasets["nm_observer"][0]["observer_status"] == "not_configured"


def test_fresh_observation_merges_only_direct_map_state(tmp_path: Path) -> None:
    observed_at = dt.datetime(2026, 7, 31, 12, 0, tzinfo=dt.timezone.utc)
    state_path = tmp_path / "nm-state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "observed_at": observed_at.isoformat(),
                "map_started_at": "2026-07-27T10:10:37+00:00",
                "ruleset_git_sha": "0123456789abcdef",
                "nms": [
                    {
                        "nm_key": "valkurm-emperor",
                        "status": "lottery_open",
                        "cooldown_opens_at": "2026-07-31T09:58:53+00:00",
                        "cooldown_remaining_seconds": 0,
                        "is_spawned": False,
                        "is_primed": False,
                        "placeholder_status": "alive",
                        "last_observed_kill_at": "2026-07-31T09:58:52+00:00",
                        "next_lottery_opportunity_at": None,
                        "effective_chance_percent": 10,
                        "effective_cooldown_seconds": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    datasets = build_public_nm_datasets(
        project_root=PROJECT_ROOT,
        state_path=state_path,
        now=observed_at + dt.timedelta(minutes=30),
    )

    emperor = next(
        row for row in datasets["nm_status"] if row["nm_key"] == "valkurm-emperor"
    )
    assert emperor["status"] == "lottery_open"
    assert emperor["data_quality"] == "direct_map_observation"
    assert emperor["last_observed_status"] is None
    assert datasets["nm_observer"][0]["observer_status"] == "fresh"
    assert datasets["nm_observer"][0]["ruleset_git_sha"] == "01234567"


def test_stale_observation_is_labeled_unknown(tmp_path: Path) -> None:
    observed_at = dt.datetime(2026, 7, 31, 8, 0, tzinfo=dt.timezone.utc)
    state_path = tmp_path / "nm-state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "observed_at": observed_at.isoformat(),
                "nms": [
                    {
                        "nm_key": "spiny-spipi",
                        "status": "cooldown_blocked",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    datasets = build_public_nm_datasets(
        project_root=PROJECT_ROOT,
        state_path=state_path,
        now=observed_at + dt.timedelta(hours=3),
    )

    spipi = next(row for row in datasets["nm_status"] if row["nm_key"] == "spiny-spipi")
    assert spipi["status"] == "unknown"
    assert spipi["last_observed_status"] == "cooldown_blocked"
    assert spipi["data_quality"] == "stale_direct_observation"
    assert datasets["nm_observer"][0]["observer_status"] == "stale"


def test_observation_rejects_non_allowlisted_fields(tmp_path: Path) -> None:
    state_path = tmp_path / "nm-state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "observed_at": "2026-07-31T12:00:00+00:00",
                "nms": [
                    {
                        "nm_key": "ose",
                        "status": "spawned",
                        "raw_payload": {"private": True},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-allowlisted fields"):
        build_public_nm_datasets(
            project_root=PROJECT_ROOT,
            state_path=state_path,
        )


def test_observation_rejects_duplicate_nm_rows(tmp_path: Path) -> None:
    state_path = tmp_path / "nm-state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "observed_at": "2026-07-31T12:00:00+00:00",
                "nms": [
                    {"nm_key": "ose", "status": "spawned"},
                    {"nm_key": "ose", "status": "unknown"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate NM observation row"):
        build_public_nm_datasets(
            project_root=PROJECT_ROOT,
            state_path=state_path,
        )
