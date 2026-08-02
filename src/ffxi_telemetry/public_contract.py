from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Dict, Optional

PUBLIC_SCHEMA_VERSION = 5
DASHBOARD_CONTRACT_VERSION = 1
DEFAULT_MAX_SNAPSHOT_AGE_SECONDS = 20 * 60


DASHBOARD_DATASET_FIELDS = {
    "progress_daily": (
        "event_date",
        "completed_fights",
        "exp_earned",
        "target_levels_reached",
        "objective_milestones",
    ),
    "progression_velocity": (
        "period_grain",
        "period_start",
        "period_end",
        "is_complete",
        "active_seconds",
        "exp_earned",
        "gil_earned",
        "exp_per_active_hour",
        "gil_per_active_hour",
    ),
    "progression_current": (
        "observed_at",
        "lease_exp_earned",
        "lease_gil_earned",
        "lease_exp_per_active_hour",
        "lease_gil_per_active_hour",
        "metric_quality",
    ),
    "combat_daily": (
        "event_date",
        "completed_fights",
        "proactive_engagements",
        "reactive_engagements",
        "attack_issued",
        "attack_rejections",
        "attack_rejection_rate",
        "target_cycle_errors",
        "weapon_skills",
        "job_abilities",
        "combat_spells",
    ),
    "navigation_daily": (
        "event_date",
        "camp_relocations",
        "zone_transitions",
        "line_of_sight_nudges",
        "navigation_failures",
        "navigation_retries",
        "collision_probes",
        "successful_collision_probes",
        "partial_progress_probes",
        "stalled_probes",
        "service_teleport_operations",
    ),
    "mcp_operations": (
        "operation",
        "operation_count",
        "successful_operations",
        "failed_operations",
        "success_rate",
    ),
    "commit_performance": (
        "source_git_sha",
        "git_sha_provenance",
        "first_event_date",
        "last_event_date",
        "completed_fights",
        "mcp_operations",
    ),
    "data_quality": (
        "source",
        "bronze_rows",
        "duplicate_event_ids",
        "latest_session_malformed_rows",
        "latest_session_reconciled",
        "latest_event_time",
        "latest_ingested_at",
    ),
    "nm_status": (
        "nm_key",
        "display_name",
        "zone",
        "status",
        "recorded_defeat_count",
        "last_observed_kill_at",
        "data_quality",
    ),
    "nm_observer": (
        "observer_status",
        "observed_at",
        "tracked_nm_count",
        "observed_nm_count",
        "refresh_cadence",
    ),
}

DASHBOARD_MINIMUM_ROWS = {
    **{name: 1 for name in DASHBOARD_DATASET_FIELDS},
    "nm_status": 20,
}


def _parse_timestamp(value: object) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError("public snapshot generated_at must be an ISO timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("public snapshot generated_at must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("public snapshot generated_at must include a timezone")
    return parsed.astimezone(dt.timezone.utc)


def validate_dashboard_datasets(datasets: object) -> Dict[str, int]:
    if not isinstance(datasets, Mapping):
        raise ValueError("public snapshot datasets must be an object")

    row_counts: Dict[str, int] = {}
    for name, required_fields in DASHBOARD_DATASET_FIELDS.items():
        rows = datasets.get(name)
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            raise ValueError(f"required dashboard dataset is missing or invalid: {name}")
        minimum_rows = DASHBOARD_MINIMUM_ROWS[name]
        if len(rows) < minimum_rows:
            raise ValueError(
                f"required dashboard dataset {name} has {len(rows)} rows; "
                f"expected at least {minimum_rows}"
            )
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise ValueError(f"dashboard dataset {name}[{index}] must be an object")
            missing = [field for field in required_fields if field not in row]
            if missing:
                raise ValueError(
                    f"dashboard dataset {name}[{index}] is missing fields: "
                    + ", ".join(missing)
                )
        row_counts[name] = len(rows)
    return row_counts


def build_dashboard_contract(datasets: object) -> Dict[str, object]:
    row_counts = validate_dashboard_datasets(datasets)
    return {
        "version": DASHBOARD_CONTRACT_VERSION,
        "producer": "ffxi-telemetry refresh-public",
        "required_datasets": list(DASHBOARD_DATASET_FIELDS),
        "dataset_row_counts": row_counts,
        "single_snapshot": True,
    }


def validate_dashboard_contract(
    snapshot: Mapping[str, object],
    *,
    now: Optional[dt.datetime] = None,
    max_age_seconds: int = DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
) -> Dict[str, int]:
    if snapshot.get("schema_version") != PUBLIC_SCHEMA_VERSION:
        raise ValueError(
            f"public snapshot schema_version must be {PUBLIC_SCHEMA_VERSION}"
        )

    row_counts = validate_dashboard_datasets(snapshot.get("datasets"))
    contract = snapshot.get("dashboard_contract")
    if not isinstance(contract, Mapping):
        raise ValueError("public snapshot is missing its dashboard contract")
    if contract.get("version") != DASHBOARD_CONTRACT_VERSION:
        raise ValueError(
            f"dashboard contract version must be {DASHBOARD_CONTRACT_VERSION}"
        )
    if contract.get("single_snapshot") is not True:
        raise ValueError("dashboard contract must declare a single snapshot")
    if contract.get("required_datasets") != list(DASHBOARD_DATASET_FIELDS):
        raise ValueError("dashboard contract required_datasets does not match the producer")
    if contract.get("dataset_row_counts") != row_counts:
        raise ValueError("dashboard contract row counts do not match the snapshot")

    generated_at = _parse_timestamp(snapshot.get("generated_at"))
    reference = now or dt.datetime.now(dt.timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=dt.timezone.utc)
    reference = reference.astimezone(dt.timezone.utc)
    age_seconds = (reference - generated_at).total_seconds()
    if age_seconds < -300:
        raise ValueError("public snapshot generated_at is unexpectedly in the future")
    if age_seconds > max_age_seconds:
        raise ValueError(
            f"public snapshot is stale at publish time: {int(age_seconds)} seconds old"
        )
    return row_counts
