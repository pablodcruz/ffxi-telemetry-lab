from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Dict, List

import duckdb

PUBLIC_QUERIES = {
    "progress_daily": """
        select
          cast(event_date as varchar) event_date,
          sum(completed_fights)::bigint completed_fights,
          sum(exp_earned)::bigint exp_earned,
          case
            when count_if(exp_metric_quality = 'state_observer_counter') > 0
            then 'state_observer_counter'
            else 'unavailable'
          end exp_metric_quality,
          sum(target_levels_reached)::bigint target_levels_reached,
          max(maximum_level_reached)::bigint maximum_level_reached,
          sum(objective_milestones)::bigint objective_milestones,
          sum(zone_transitions)::bigint zone_transitions
        from gold.gold_autonomous_progression
        group by event_date
        order by event_date
    """,
    "combat_daily": """
        select
          cast(event_date as varchar) event_date,
          sum(completed_fights)::bigint completed_fights,
          sum(proactive_engagements)::bigint proactive_engagements,
          sum(reactive_engagements)::bigint reactive_engagements,
          sum(attack_issued)::bigint attack_issued,
          sum(attack_rejections)::bigint attack_rejections,
          sum(attack_rejections)::double
            / nullif(sum(attack_issued) + sum(attack_rejections), 0)
            attack_rejection_rate,
          sum(target_cycle_errors)::bigint target_cycle_errors,
          sum(weapon_skills)::bigint weapon_skills,
          sum(job_abilities)::bigint job_abilities,
          sum(combat_spells)::bigint combat_spells,
          max(aggro_response_p95_ms) aggro_response_p95_ms,
          max(aggro_response_max_ms) aggro_response_max_ms,
          max(handoff_queue_p95_ms) handoff_queue_p95_ms,
          max(handoff_queue_max_ms) handoff_queue_max_ms,
          sum(deaths)::bigint deaths,
          sum(recoveries)::bigint recoveries,
          case
            when count_if(death_recovery_metric_quality = 'state_observer_counter') > 0
            then 'state_observer_counter'
            else 'unavailable'
          end death_recovery_metric_quality
        from gold.gold_combat_reliability
        group by event_date
        order by event_date
    """,
    "navigation_daily": """
        select
          cast(event_date as varchar) event_date,
          sum(camp_relocations)::bigint camp_relocations,
          sum(zone_transitions)::bigint zone_transitions,
          sum(line_of_sight_nudges)::bigint line_of_sight_nudges,
          sum(navigation_failures)::bigint navigation_failures,
          sum(navigation_retries)::bigint navigation_retries,
          sum(collision_probes)::bigint collision_probes,
          sum(successful_collision_probes)::bigint successful_collision_probes,
          sum(partial_progress_probes)::bigint partial_progress_probes,
          sum(stalled_probes)::bigint stalled_probes,
          sum(successful_collision_probes)::double / nullif(sum(collision_probes), 0)
            collision_probe_success_rate,
          max(service_teleport_operations)::bigint service_teleport_operations
        from gold.gold_navigation_performance
        group by event_date
        order by event_date
    """,
    "mcp_operations": """
        select
          operation,
          sum(operation_count)::bigint operation_count,
          sum(successful_operations)::bigint successful_operations,
          sum(failed_operations)::bigint failed_operations,
          sum(successful_operations)::double / nullif(sum(operation_count), 0)
            success_rate,
          max(duration_p95_ms) duration_p95_ms,
          max(duration_max_ms) duration_max_ms
        from gold.gold_mcp_operation_reliability
        group by operation
        order by operation_count desc, operation
    """,
    "commit_performance": """
        select
          substr(source_git_sha, 1, 8) source_git_sha,
          git_sha_provenance,
          cast(first_event_date as varchar) first_event_date,
          cast(last_event_date as varchar) last_event_date,
          completed_fights,
          attack_rejection_rate,
          supervisor_errors,
          mcp_operations,
          mcp_failure_rate,
          navigation_failures
        from gold.gold_performance_by_git_commit
        where source_git_sha is not null
        order by first_event_date, source_git_sha
    """,
    "data_quality": """
        select
          source,
          bronze_rows,
          distinct_event_ids,
          null_event_ids,
          null_event_times,
          duplicate_event_ids,
          cast(earliest_event_time as varchar) earliest_event_time,
          cast(latest_event_time as varchar) latest_event_time,
          cast(latest_ingested_at as varchar) latest_ingested_at,
          latest_session_valid_rows,
          latest_session_malformed_rows,
          latest_session_reconciled
        from gold.gold_data_quality
        order by source
    """,
}


def _records(connection: duckdb.DuckDBPyConnection, query: str) -> List[Dict[str, object]]:
    cursor = connection.execute(query)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_public_snapshot(duckdb_path: Path) -> Dict[str, object]:
    if not duckdb_path.is_file():
        raise ValueError(f"DuckDB database does not exist: {duckdb_path}")
    connection = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        datasets = {name: _records(connection, query) for name, query in PUBLIC_QUERIES.items()}
    finally:
        connection.close()
    quality = datasets["data_quality"]
    coverage_start = min(
        (row["earliest_event_time"] for row in quality if row["earliest_event_time"]),
        default=None,
    )
    coverage_end = max(
        (row["latest_event_time"] for row in quality if row["latest_event_time"]),
        default=None,
    )
    return {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "privacy": {
            "classification": "public_aggregate",
            "contains_raw_payloads": False,
            "contains_agent_ids": False,
            "contains_lease_ids": False,
            "git_shas_truncated": True,
        },
        "coverage": {
            "earliest_event_time": coverage_start,
            "latest_event_time": coverage_end,
        },
        "metric_notes": {
            "exp_earned": (
                "Available only for state-observer-covered periods; historical "
                "fight events have no EXP delta."
            ),
            "deaths_recoveries": "Available only for state-observer-covered periods.",
            "job": "Unavailable in the current event and state contracts.",
            "teleport_dependency": (
                "Service-teleport operation count is a proxy; event causality is unavailable."
            ),
            "git_attribution": (
                "Historical SHAs are inferred from commit time; future collection observes "
                "HEAD at ingestion."
            ),
        },
        "datasets": datasets,
    }


def export_public_snapshot(duckdb_path: Path, output: str) -> Dict[str, object]:
    snapshot = build_public_snapshot(duckdb_path)
    destination = Path(output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    os.replace(temporary, destination)
    return {
        "output": str(destination),
        "generated_at": snapshot["generated_at"],
        "datasets": {name: len(rows) for name, rows in snapshot["datasets"].items()},
    }
