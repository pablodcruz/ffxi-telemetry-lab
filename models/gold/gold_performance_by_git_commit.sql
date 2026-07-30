with combat as (
    select
        source_git_sha,
        any_value(git_sha_provenance) as git_sha_provenance,
        min(event_date) as first_event_date,
        max(event_date) as last_event_date,
        sum(completed_fights) as completed_fights,
        sum(attack_rejections) as attack_rejections,
        sum(attack_issued) as attack_issued,
        sum(supervisor_errors) as supervisor_errors
    from {{ ref('gold_combat_reliability') }}
    group by source_git_sha
),
mcp as (
    select
        source_git_sha,
        sum(operation_count) as mcp_operations,
        sum(failed_operations) as mcp_failures
    from {{ ref('gold_mcp_operation_reliability') }}
    group by source_git_sha
),
navigation as (
    select
        source_git_sha,
        sum(camp_relocations) as camp_relocations,
        sum(zone_transitions) as zone_transitions,
        sum(line_of_sight_nudges) as line_of_sight_nudges,
        sum(navigation_failures) as navigation_failures
    from {{ ref('gold_navigation_performance') }}
    group by source_git_sha
)
select
    c.source_git_sha,
    c.git_sha_provenance,
    c.first_event_date,
    c.last_event_date,
    c.completed_fights,
    c.attack_rejections,
    c.attack_issued,
    c.attack_rejections::double / nullif(c.attack_issued + c.attack_rejections, 0)
        as attack_rejection_rate,
    c.supervisor_errors,
    coalesce(m.mcp_operations, 0) as mcp_operations,
    coalesce(m.mcp_failures, 0) as mcp_failures,
    m.mcp_failures::double / nullif(m.mcp_operations, 0) as mcp_failure_rate,
    coalesce(n.camp_relocations, 0) as camp_relocations,
    coalesce(n.zone_transitions, 0) as zone_transitions,
    coalesce(n.line_of_sight_nudges, 0) as line_of_sight_nudges,
    coalesce(n.navigation_failures, 0) as navigation_failures
from combat c
left join mcp m using (source_git_sha)
left join navigation n using (source_git_sha)
