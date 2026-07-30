with event_metrics as (
    select
        event_date,
        lease_id,
        source_git_sha,
        any_value(git_sha_provenance) as git_sha_provenance,
        count_if(event_type = 'fight_complete') as completed_fights,
        count_if(event_type = 'attack_issued' and engagement_mode = 'proactive')
            as proactive_engagements,
        count_if(event_type = 'attack_issued' and engagement_mode = 'reactive')
            as reactive_engagements,
        count_if(event_type = 'attack_issued') as attack_issued,
        count_if(event_type = 'attack_rejected') as attack_rejections,
        count_if(event_type = 'target_cycle_error') as target_cycle_errors,
        count_if(event_type = 'weapon_skill') as weapon_skills,
        count_if(event_type = 'job_ability') as job_abilities,
        count_if(event_type = 'combat_spell') as combat_spells,
        count_if(event_type = 'farm_supervisor_error') as supervisor_errors,
        quantile_cont(aggro_response_ms, 0.50)
            filter (where aggro_response_ms is not null) as aggro_response_p50_ms,
        quantile_cont(aggro_response_ms, 0.95)
            filter (where aggro_response_ms is not null) as aggro_response_p95_ms,
        max(aggro_response_ms) as aggro_response_max_ms,
        quantile_cont(handoff_queue_ms, 0.50)
            filter (where handoff_queue_ms is not null) as handoff_queue_p50_ms,
        quantile_cont(handoff_queue_ms, 0.95)
            filter (where handoff_queue_ms is not null) as handoff_queue_p95_ms,
        max(handoff_queue_ms) as handoff_queue_max_ms
    from {{ ref('silver_supervisor_events') }}
    group by event_date, lease_id, source_git_sha
),
state_metrics as (
    select
        observation_date as event_date,
        lease_id,
        max(deaths) as deaths,
        max(recoveries) as recoveries,
        count(*) as state_snapshot_count
    from {{ ref('silver_state_snapshots') }}
    group by observation_date, lease_id
)
select
    e.*,
    case
        when e.attack_issued + e.attack_rejections > 0
        then e.attack_rejections::double / (e.attack_issued + e.attack_rejections)
        else null
    end as attack_rejection_rate,
    s.deaths,
    s.recoveries,
    case when s.state_snapshot_count > 0 then 'state_observer_counter' else 'unavailable'
        end as death_recovery_metric_quality,
    coalesce(s.state_snapshot_count, 0) as state_snapshot_count
from event_metrics e
left join state_metrics s using (event_date, lease_id)
