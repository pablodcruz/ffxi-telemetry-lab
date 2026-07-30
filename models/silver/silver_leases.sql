select
    lease_id,
    min(event_time) as lease_started_at,
    max(event_time) as lease_last_event_at,
    date_diff('second', min(event_time), max(event_time)) as observed_duration_seconds,
    count(*) as event_count,
    count_if(event_type = 'fight_complete') as completed_fights,
    max(case when event_type = 'farm_supervisor_armed' then zone_id end) as configured_zone_id,
    arg_min(agent_id, event_time) filter (where agent_id is not null) as agent_id,
    arg_min(source_git_sha, event_time) filter (where source_git_sha is not null)
        as starting_source_git_sha,
    arg_max(source_git_sha, event_time) filter (where source_git_sha is not null)
        as ending_source_git_sha
from {{ ref('silver_supervisor_events') }}
where lease_id is not null
group by lease_id
