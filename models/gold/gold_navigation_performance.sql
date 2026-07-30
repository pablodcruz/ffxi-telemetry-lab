with supervisor_navigation as (
    select
        event_date,
        lease_id,
        source_git_sha,
        any_value(git_sha_provenance) as git_sha_provenance,
        max(coalesce(zone_id, from_zone_id, to_zone_id)) as zone_id,
        count_if(event_type = 'camp_relocated') as camp_relocations,
        count_if(event_type = 'zone_transition_complete') as zone_transitions,
        count_if(event_type = 'line_of_sight_nudge') as line_of_sight_nudges,
        count_if(event_type in (
            'farm_supervisor_error',
            'nm_route_safe_exit_blocked',
            'nm_route_sweep_blocked',
            'nm_route_transition_support_unavailable'
        )) as navigation_failures,
        count_if(event_type in (
            'line_of_sight_nudge_race',
            'engagement_reissued',
            'reactive_attack_reissued',
            'recovery_command_reissued'
        )) as navigation_retries
    from {{ ref('silver_supervisor_events') }}
    group by event_date, lease_id, source_git_sha
),
probe_metrics as (
    select
        event_date,
        cast(null as varchar) as lease_id,
        source_git_sha,
        any_value(git_sha_provenance) as git_sha_provenance,
        cast(null as integer) as zone_id,
        count(*) as collision_probes,
        count_if(lower(coalesce(outcome, '')) = 'arrived')
            as successful_collision_probes,
        count_if(lower(coalesce(outcome, '')) = 'partial_progress')
            as partial_progress_probes,
        count_if(lower(coalesce(outcome, '')) = 'stalled')
            as stalled_probes,
        avg(displacement) as average_probe_displacement,
        avg(remaining_distance) as average_remaining_distance
    from {{ ref('silver_navigation_attempts') }}
    group by event_date, source_git_sha
),
teleport_metrics as (
    select
        event_date,
        source_git_sha,
        count(*) as service_teleport_operations
    from {{ ref('silver_agent_actions') }}
    where operation = 'service_teleport'
    group by event_date, source_git_sha
),
combined as (
    select
        event_date, lease_id, source_git_sha, git_sha_provenance, zone_id,
        camp_relocations, zone_transitions, line_of_sight_nudges,
        navigation_failures, navigation_retries,
        0::bigint as collision_probes,
        0::bigint as successful_collision_probes,
        0::bigint as partial_progress_probes,
        0::bigint as stalled_probes,
        null::double as average_probe_displacement,
        null::double as average_remaining_distance
    from supervisor_navigation
    union all
    select
        event_date, lease_id, source_git_sha, git_sha_provenance, zone_id,
        0, 0, 0, 0, 0,
        collision_probes, successful_collision_probes,
        partial_progress_probes, stalled_probes,
        average_probe_displacement, average_remaining_distance
    from probe_metrics
)
select
    c.event_date,
    c.lease_id,
    c.zone_id,
    c.source_git_sha,
    c.git_sha_provenance,
    c.camp_relocations,
    c.zone_transitions,
    c.line_of_sight_nudges,
    c.navigation_failures,
    c.navigation_retries,
    c.collision_probes,
    c.successful_collision_probes,
    c.partial_progress_probes,
    c.stalled_probes,
    case when c.collision_probes > 0
        then c.successful_collision_probes::double / c.collision_probes
        else null end as collision_probe_success_rate,
    c.average_probe_displacement,
    c.average_remaining_distance,
    coalesce(t.service_teleport_operations, 0) as service_teleport_operations,
    'operation count is a dependency proxy; causality is unavailable'
        as teleport_metric_note
from combined c
left join teleport_metrics t
    on c.event_date = t.event_date
    and c.source_git_sha is not distinct from t.source_git_sha
