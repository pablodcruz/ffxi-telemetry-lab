with event_progress as (
    select
        event_date,
        lease_id,
        max(l.configured_zone_id) as zone_id,
        source_git_sha,
        any_value(git_sha_provenance) as git_sha_provenance,
        count_if(event_type = 'fight_complete') as completed_fights,
        count_if(event_type = 'target_level_reached') as target_levels_reached,
        max(reached_level) filter (where event_type = 'target_level_reached')
            as maximum_level_reached,
        count_if(event_type = 'quest_item_obtained') as objective_milestones,
        count_if(event_type = 'zone_transition_complete') as zone_transitions
    from {{ ref('silver_supervisor_events') }} e
    left join {{ ref('silver_leases') }} l using (lease_id)
    group by event_date, lease_id, source_git_sha
),
state_progress as (
    select
        observation_date as event_date,
        lease_id,
        arg_max(active_zone_id, observed_at) as zone_id,
        arg_max(source_git_sha, observed_at) as source_git_sha,
        arg_max(git_sha_provenance, observed_at) as git_sha_provenance,
        max(exp_earned) as exp_earned_observed,
        max(fights_completed) as fights_completed_observed,
        max(elapsed_seconds) as elapsed_seconds_observed,
        count(*) as state_snapshot_count
    from {{ ref('silver_state_snapshots') }}
    group by observation_date, lease_id
)
select
    coalesce(e.event_date, s.event_date) as event_date,
    coalesce(e.lease_id, s.lease_id) as lease_id,
    coalesce(e.zone_id, s.zone_id) as zone_id,
    cast(null as varchar) as job_name,
    coalesce(e.source_git_sha, s.source_git_sha) as source_git_sha,
    coalesce(e.git_sha_provenance, s.git_sha_provenance, 'unavailable')
        as git_sha_provenance,
    coalesce(e.completed_fights, 0) as completed_fights,
    case
        when s.elapsed_seconds_observed > 0
        then coalesce(s.fights_completed_observed, e.completed_fights, 0)
            / (s.elapsed_seconds_observed / 3600.0)
        when l.observed_duration_seconds > 0
        then coalesce(e.completed_fights, 0) / (l.observed_duration_seconds / 3600.0)
        else null
    end as fights_per_hour,
    s.exp_earned_observed as exp_earned,
    case when s.state_snapshot_count > 0 then 'state_observer_counter' else 'unavailable'
        end as exp_metric_quality,
    coalesce(e.target_levels_reached, 0) as target_levels_reached,
    e.maximum_level_reached,
    coalesce(e.objective_milestones, 0) as objective_milestones,
    coalesce(e.zone_transitions, 0) as zone_transitions,
    coalesce(s.state_snapshot_count, 0) as state_snapshot_count,
    'job dimension unavailable in current event/state contracts' as job_metric_note
from event_progress e
full outer join state_progress s
    on e.event_date = s.event_date and e.lease_id = s.lease_id
left join {{ ref('silver_leases') }} l
    on coalesce(e.lease_id, s.lease_id) = l.lease_id
