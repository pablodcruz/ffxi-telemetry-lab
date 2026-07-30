from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

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
    "progression_velocity": """
        with valid_intervals as (
          select
            observed_at,
            active_seconds,
            exp_earned_delta,
            gil_earned_delta
          from gold.gold_progression_velocity
          where metric_quality = 'observed_delta'
        ),
        bucketed as (
          select
            'hour' period_grain,
            date_trunc('hour', observed_at) period_start,
            active_seconds,
            exp_earned_delta,
            gil_earned_delta
          from valid_intervals
          union all
          select
            'day' period_grain,
            date_trunc('day', observed_at) period_start,
            active_seconds,
            exp_earned_delta,
            gil_earned_delta
          from valid_intervals
          union all
          select
            'week' period_grain,
            date_trunc('week', observed_at) period_start,
            active_seconds,
            exp_earned_delta,
            gil_earned_delta
          from valid_intervals
        ),
        aggregated as (
          select
            period_grain,
            period_start,
            sum(active_seconds)::bigint active_seconds,
            sum(exp_earned_delta)::bigint exp_earned,
            sum(gil_earned_delta)::bigint gil_earned,
            sum(exp_earned_delta) * 3600.0 / nullif(sum(active_seconds), 0)
              exp_per_active_hour,
            sum(gil_earned_delta) * 3600.0 / nullif(sum(active_seconds), 0)
              gil_per_active_hour,
            count(*)::bigint observed_intervals
          from bucketed
          group by period_grain, period_start
        )
        select
          period_grain,
          cast(period_start as varchar) period_start,
          cast(
            case period_grain
              when 'hour' then period_start + interval 1 hour
              when 'day' then period_start + interval 1 day
              else period_start + interval 7 day
            end
            as varchar
          ) period_end,
          case period_grain
            when 'hour' then period_start + interval 1 hour <= current_timestamp
            when 'day' then period_start + interval 1 day <= current_timestamp
            else period_start + interval 7 day <= current_timestamp
          end is_complete,
          active_seconds,
          exp_earned,
          gil_earned,
          exp_per_active_hour,
          gil_per_active_hour,
          observed_intervals
        from aggregated
        where
          period_grain <> 'hour'
          or period_start >= current_timestamp - interval 90 day
        order by
          case period_grain when 'hour' then 1 when 'day' then 2 else 3 end,
          period_start
    """,
    "progression_current": """
        select
          cast(observed_at as varchar) observed_at,
          elapsed_seconds,
          lease_exp_earned,
          lease_gil_earned,
          lease_exp_per_active_hour,
          lease_gil_per_active_hour,
          metric_quality
        from gold.gold_progression_velocity
        qualify row_number() over (order by observed_at desc, event_id desc) = 1
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
        "schema_version": 2,
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
                "EXP trends use consecutive state-observer counter deltas; historical "
                "fight events have no EXP delta."
            ),
            "gil_earned": (
                "Gil trends use consecutive state-observer counter deltas; historical "
                "fight events have no gil delta."
            ),
            "progression_velocity": (
                "Per-active-hour rates divide summed counter deltas by summed supervisor "
                "elapsed-time deltas. Rates are never summed. Intervals with counter resets, "
                "non-positive active time, or observation gaps over 75 minutes are excluded."
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


def _write_snapshot(snapshot: Dict[str, object], output: str) -> Path:
    destination = Path(output).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    os.replace(temporary, destination)
    return destination


def export_public_snapshot(
    duckdb_path: Path,
    output: str,
    site_output: Optional[str] = None,
) -> Dict[str, object]:
    snapshot = build_public_snapshot(duckdb_path)
    destination = _write_snapshot(snapshot, output)
    site_destination = _write_snapshot(snapshot, site_output) if site_output else None
    return {
        "output": str(destination),
        "site_output": str(site_destination) if site_destination else None,
        "generated_at": snapshot["generated_at"],
        "datasets": {name: len(rows) for name, rows in snapshot["datasets"].items()},
    }
