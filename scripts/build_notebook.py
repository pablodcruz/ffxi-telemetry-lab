from __future__ import annotations

from pathlib import Path

import duckdb
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "warehouse" / "telemetry.duckdb"
NOTEBOOK = ROOT / "notebooks" / "ffxi_telemetry_analysis.ipynb"


def scalar(connection: duckdb.DuckDBPyConnection, query: str):
    return connection.execute(query).fetchone()[0]


def build() -> Path:
    connection = duckdb.connect(str(DATABASE), read_only=True)
    try:
        fights = scalar(
            connection,
            "select sum(completed_fights) from gold.gold_autonomous_progression",
        )
        mcp_operations = scalar(
            connection,
            "select sum(operation_count) from gold.gold_mcp_operation_reliability",
        )
        mcp_failures = scalar(
            connection,
            "select sum(failed_operations) from gold.gold_mcp_operation_reliability",
        )
        attacks = scalar(
            connection,
            "select sum(attack_issued) from gold.gold_combat_reliability",
        )
        rejected = scalar(
            connection,
            "select sum(attack_rejections) from gold.gold_combat_reliability",
        )
        arrived, partial, stalled = connection.execute(
            """
            select
              sum(successful_collision_probes),
              sum(partial_progress_probes),
              sum(stalled_probes)
            from gold.gold_navigation_performance
            """
        ).fetchone()
        probes = (arrived or 0) + (partial or 0) + (stalled or 0)
        malformed = scalar(
            connection,
            "select sum(latest_session_malformed_rows) from gold.gold_data_quality",
        )
    finally:
        connection.close()

    attack_rate = rejected / (attacks + rejected) if attacks + rejected else 0
    mcp_success = 1 - (mcp_failures / mcp_operations) if mcp_operations else 0
    probe_arrival = arrived / probes if probes else 0

    notebook = nbf.v4.new_notebook()
    notebook["metadata"]["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook["metadata"]["language_info"] = {"name": "python", "version": "3.9"}
    notebook["cells"] = [
        nbf.v4.new_markdown_cell(
            f"""# FFXI Telemetry Lab analysis

## tl;dr

- The frozen backfill contains **{fights:,} completed fights** and
  **{mcp_operations:,} MCP operations**.
- MCP operation success is **{mcp_success:.2%}**; the attack rejection rate is
  **{attack_rate:.2%}**.
- Navigation probes reached their destination in **{arrived:,} of {probes:,}**
  attempts (**{probe_arrival:.1%}**), with **{partial:,} partial-progress** and
  **{stalled:,} stalled** outcomes.
- The latest ingestion session quarantined **{malformed:,} malformed rows** and
  reconciled exactly to its frozen source boundaries.
- Historical EXP, deaths, and recoveries are unavailable because event history
  does not carry those counters. They become available only during state-observer
  coverage.
"""
        ),
        nbf.v4.new_markdown_cell(
            """## Context & Methods

This companion notebook reads only tested Gold models from the local DuckDB
database. It never queries raw payloads or the gameplay project. Historical Git
SHAs are inferred from the most recent commit at or before each event timestamp;
observer and incremental rows use the HEAD observed at ingestion.

### Key Assumptions

- `fight_complete` is the authoritative historical fight count.
- A successful collision probe has outcome `arrived`; `partial_progress` and
  `stalled` remain separate outcomes.
- Service-teleport operations are a dependency proxy, not proof of a navigation
  cause.
- Job is unavailable in the current event/state contracts.
"""
        ),
        nbf.v4.new_markdown_cell("## Data\n\n### 1. Load tested Gold models"),
        nbf.v4.new_code_cell(
            """from pathlib import Path

import duckdb
import plotly.express as px

ROOT = Path.cwd()
DB_PATH = ROOT / "data" / "warehouse" / "telemetry.duckdb"
assert DB_PATH.is_file(), "Run backfill, prepare-warehouse, and dbt build first."
connection = duckdb.connect(str(DB_PATH), read_only=True)
"""
        ),
        nbf.v4.new_markdown_cell("### 2. Verify data quality"),
        nbf.v4.new_code_cell(
            """quality = connection.execute(
    '''
    select source, bronze_rows, distinct_event_ids, null_event_times,
           duplicate_event_ids, latest_session_malformed_rows,
           latest_session_reconciled
    from gold.gold_data_quality
    order by source
    '''
).df()
assert quality["duplicate_event_ids"].sum() == 0
assert quality["null_event_times"].sum() == 0
assert quality["latest_session_reconciled"].all()
quality
"""
        ),
        nbf.v4.new_markdown_cell("## Results\n\n### 3. Autonomous progression"),
        nbf.v4.new_code_cell(
            """progress = connection.execute(
    '''
    select event_date,
           sum(completed_fights) completed_fights,
           sum(target_levels_reached) target_levels_reached,
           sum(objective_milestones) objective_milestones,
           sum(exp_earned) exp_earned,
           max(exp_metric_quality) exp_metric_quality
    from gold.gold_autonomous_progression
    group by event_date
    order by event_date
    '''
).df()
progress
"""
        ),
        nbf.v4.new_code_cell(
            """progress_plot = progress.melt(
    id_vars=["event_date"],
    value_vars=["completed_fights", "target_levels_reached", "objective_milestones"],
    var_name="metric",
    value_name="count",
)
fig = px.line(
    progress_plot,
    x="event_date",
    y="count",
    color="metric",
    markers=True,
    title="Autonomous progression by day",
)
fig.update_layout(xaxis_title=None, yaxis_title="Events", template="plotly_white")
fig.show()
"""
        ),
        nbf.v4.new_markdown_cell("### 4. Combat reliability"),
        nbf.v4.new_code_cell(
            """combat = connection.execute(
    '''
    select event_date,
           sum(completed_fights) completed_fights,
           sum(proactive_engagements) proactive_engagements,
           sum(reactive_engagements) reactive_engagements,
           sum(attack_issued) attack_issued,
           sum(attack_rejections) attack_rejections,
           sum(target_cycle_errors) target_cycle_errors,
           sum(weapon_skills) weapon_skills,
           sum(job_abilities) job_abilities,
           sum(combat_spells) combat_spells,
           max(aggro_response_p95_ms) aggro_response_p95_ms,
           max(handoff_queue_p95_ms) handoff_queue_p95_ms
    from gold.gold_combat_reliability
    group by event_date
    order by event_date
    '''
).df()
combat["attack_rejection_rate"] = (
    combat["attack_rejections"]
    / (combat["attack_issued"] + combat["attack_rejections"])
)
combat
"""
        ),
        nbf.v4.new_code_cell(
            """engagements = combat.melt(
    id_vars=["event_date"],
    value_vars=["proactive_engagements", "reactive_engagements"],
    var_name="mode",
    value_name="engagements",
)
fig = px.bar(
    engagements,
    x="event_date",
    y="engagements",
    color="mode",
    barmode="stack",
    title="Engagement mix by day",
    color_discrete_sequence=["#2563EB", "#D4A72C"],
)
fig.update_layout(xaxis_title=None, yaxis_title="Engagements", template="plotly_white")
fig.show()
"""
        ),
        nbf.v4.new_markdown_cell("### 5. Navigation performance"),
        nbf.v4.new_code_cell(
            """navigation = connection.execute(
    '''
    select event_date,
           sum(collision_probes) collision_probes,
           sum(successful_collision_probes) arrived,
           sum(partial_progress_probes) partial_progress,
           sum(stalled_probes) stalled,
           sum(camp_relocations) camp_relocations,
           sum(zone_transitions) zone_transitions,
           sum(line_of_sight_nudges) line_of_sight_nudges,
           sum(navigation_failures) navigation_failures,
           sum(navigation_retries) navigation_retries,
           max(service_teleport_operations) service_teleport_operations
    from gold.gold_navigation_performance
    group by event_date
    order by event_date
    '''
).df()
navigation
"""
        ),
        nbf.v4.new_code_cell(
            """outcomes = navigation[["arrived", "partial_progress", "stalled"]].sum().reset_index()
outcomes.columns = ["outcome", "attempts"]
fig = px.bar(
    outcomes,
    x="attempts",
    y="outcome",
    orientation="h",
    title="Collision probe outcomes",
    color_discrete_sequence=["#2563EB"],
)
fig.update_layout(xaxis_title="Attempts", yaxis_title=None, template="plotly_white")
fig.show()
"""
        ),
        nbf.v4.new_markdown_cell("### 6. MCP reliability and Git attribution"),
        nbf.v4.new_code_cell(
            """mcp = connection.execute(
    '''
    select operation,
           sum(operation_count) operation_count,
           sum(failed_operations) failed_operations,
           sum(successful_operations)::double / nullif(sum(operation_count), 0)
             as success_rate,
           max(duration_p95_ms) duration_p95_ms
    from gold.gold_mcp_operation_reliability
    group by operation
    order by operation_count desc
    limit 15
    '''
).df()
mcp
"""
        ),
        nbf.v4.new_code_cell(
            """by_commit = connection.execute(
    '''
    select substr(source_git_sha, 1, 8) source_git_sha,
           git_sha_provenance,
           completed_fights,
           attack_rejection_rate,
           mcp_operations,
           mcp_failure_rate,
           navigation_failures
    from gold.gold_performance_by_git_commit
    order by first_event_date, source_git_sha
    '''
).df()
by_commit
"""
        ),
        nbf.v4.new_markdown_cell(
            f"""## Takeaways

1. **Control is broadly reliable:** {mcp_operations:,} operations completed at
   {mcp_success:.2%} success across the backfill window.
2. **Combat has a measurable retry cost:** {rejected:,} rejected attacks against
   {attacks:,} issued attacks produce a {attack_rate:.2%} rejection rate.
3. **Navigation is mixed rather than binary:** {arrived:,} probes arrived,
   {partial:,} made partial progress, and {stalled:,} stalled. Treating partial
   progress as success would overstate reliability.
4. **Coverage labels matter:** no historical EXP/death/recovery series is claimed.
   Those counters begin only when the state observer is running.
5. **Attribution is directional:** historical commit comparisons are useful for
   investigation but remain inferred, not authoritative.
"""
        ),
        nbf.v4.new_code_cell("connection.close()"),
    ]
    NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, NOTEBOOK)
    return NOTEBOOK


if __name__ == "__main__":
    print(build())
