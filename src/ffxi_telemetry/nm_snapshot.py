from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

NM_STATE_ENV = "TELEMETRY_NM_STATE_PATH"
NM_STALE_AFTER_SECONDS = 2 * 60 * 60
VALID_STATUSES = {
    "spawned",
    "primed",
    "cooldown_blocked",
    "lottery_open",
    "unknown",
}
ROOT_ALLOWED_KEYS = {
    "schema_version",
    "observed_at",
    "map_started_at",
    "ruleset_git_sha",
    "nms",
}
ROW_ALLOWED_KEYS = {
    "nm_key",
    "status",
    "cooldown_opens_at",
    "cooldown_remaining_seconds",
    "is_spawned",
    "is_primed",
    "placeholder_status",
    "last_observed_kill_at",
    "next_lottery_opportunity_at",
    "effective_chance_percent",
    "effective_cooldown_seconds",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_timestamp(value: object) -> Optional[dt.datetime]:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _load_catalog(project_root: Path) -> Dict[str, object]:
    path = project_root / "site/public/data/nm_catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or not isinstance(catalog.get("nms"), list):
        raise ValueError("NM catalog must contain an nms list")
    rows = catalog["nms"]
    keys = [row.get("nm_key") for row in rows if isinstance(row, dict)]
    if len(rows) != 20 or len(keys) != 20 or len(set(keys)) != 20:
        raise ValueError("NM catalog must contain exactly 20 uniquely keyed monsters")
    return catalog


def _load_observation(path: Optional[Path]) -> Optional[Dict[str, object]]:
    if path is None or not path.is_file():
        return None
    observation = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(observation, dict):
        raise ValueError("NM observation root must be an object")
    unexpected_root = set(observation) - ROOT_ALLOWED_KEYS
    if unexpected_root:
        raise ValueError(
            "NM observation contains non-allowlisted fields: "
            + ", ".join(sorted(unexpected_root))
        )
    rows = observation.get("nms")
    if not isinstance(rows, list):
        raise ValueError("NM observation must contain an nms list")
    seen_keys = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("NM observation rows must be objects")
        unexpected_row = set(row) - ROW_ALLOWED_KEYS
        if unexpected_row:
            raise ValueError(
                "NM observation row contains non-allowlisted fields: "
                + ", ".join(sorted(unexpected_row))
            )
        if row.get("status") not in VALID_STATUSES:
            raise ValueError(f"invalid NM status: {row.get('status')}")
        nm_key = row.get("nm_key")
        if not isinstance(nm_key, str) or not nm_key:
            raise ValueError("NM observation row is missing nm_key")
        if nm_key in seen_keys:
            raise ValueError(f"duplicate NM observation row: {nm_key}")
        seen_keys.add(nm_key)
    if _parse_timestamp(observation.get("observed_at")) is None:
        raise ValueError("NM observation has an invalid observed_at timestamp")
    return observation


def _resolved_state_path(explicit: Optional[Path]) -> Optional[Path]:
    if explicit is not None:
        return explicit.expanduser().resolve()
    configured = os.getenv(NM_STATE_ENV)
    return Path(configured).expanduser().resolve() if configured else None


def _unknown_row(catalog_row: Dict[str, object]) -> Dict[str, object]:
    return {
        **catalog_row,
        "status": "unknown",
        "last_observed_status": None,
        "observed_at": None,
        "cooldown_opens_at": None,
        "cooldown_remaining_seconds": None,
        "is_spawned": None,
        "is_primed": None,
        "placeholder_status": "unknown",
        "last_observed_kill_at": None,
        "next_lottery_opportunity_at": None,
        "effective_chance_percent": None,
        "effective_cooldown_seconds": None,
        "data_quality": "not_observed",
    }


def build_public_nm_datasets(
    *,
    project_root: Optional[Path] = None,
    state_path: Optional[Path] = None,
    now: Optional[dt.datetime] = None,
) -> Dict[str, List[Dict[str, object]]]:
    root = project_root or _project_root()
    catalog = _load_catalog(root)
    catalog_rows = catalog["nms"]
    resolved_state = _resolved_state_path(state_path)
    observation = _load_observation(resolved_state)
    current_time = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)

    if observation is None:
        return {
            "nm_observer": [
                {
                    "observer_status": "not_configured",
                    "observed_at": None,
                    "map_started_at": None,
                    "ruleset_git_sha": None,
                    "tracked_nm_count": len(catalog_rows),
                    "observed_nm_count": 0,
                    "refresh_cadence": "hourly",
                }
            ],
            "nm_status": [_unknown_row(row) for row in catalog_rows],
        }

    observed_at = _parse_timestamp(observation.get("observed_at"))
    age_seconds = (
        max(0.0, (current_time - observed_at).total_seconds())
        if observed_at is not None
        else float("inf")
    )
    is_stale = age_seconds > NM_STALE_AFTER_SECONDS
    observed_rows = observation.get("nms", [])
    observed_by_key = {row["nm_key"]: row for row in observed_rows}
    catalog_keys = {row["nm_key"] for row in catalog_rows}
    unexpected_keys = set(observed_by_key) - catalog_keys
    if unexpected_keys:
        raise ValueError(
            "NM observation contains unknown nm_key values: "
            + ", ".join(sorted(unexpected_keys))
        )

    public_rows: List[Dict[str, object]] = []
    for catalog_row in catalog_rows:
        row = _unknown_row(catalog_row)
        observed = observed_by_key.get(catalog_row["nm_key"])
        if observed is not None:
            direct_status = observed["status"]
            row.update(
                {
                    key: observed[key]
                    for key in ROW_ALLOWED_KEYS
                    if key in observed and key not in {"nm_key", "status"}
                }
            )
            row["observed_at"] = observation.get("observed_at")
            row["last_observed_status"] = direct_status if is_stale else None
            row["status"] = "unknown" if is_stale else direct_status
            row["data_quality"] = (
                "stale_direct_observation" if is_stale else "direct_map_observation"
            )
        public_rows.append(row)

    ruleset_sha = observation.get("ruleset_git_sha")
    return {
        "nm_observer": [
            {
                "observer_status": "stale" if is_stale else "fresh",
                "observed_at": observation.get("observed_at"),
                "map_started_at": observation.get("map_started_at"),
                "ruleset_git_sha": ruleset_sha[:8] if isinstance(ruleset_sha, str) else None,
                "tracked_nm_count": len(catalog_rows),
                "observed_nm_count": len(observed_rows),
                "refresh_cadence": "hourly",
            }
        ],
        "nm_status": public_rows,
    }
