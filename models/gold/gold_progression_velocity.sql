with ordered as (
    select
        event_id,
        observed_at,
        observation_date,
        agent_id,
        lease_id,
        active_zone_id,
        phase,
        status,
        elapsed_seconds,
        exp_earned,
        gil_earned,
        source_git_sha,
        git_sha_provenance,
        lag(observed_at) over lease_observations as previous_observed_at,
        lag(elapsed_seconds) over lease_observations as previous_elapsed_seconds,
        lag(exp_earned) over lease_observations as previous_exp_earned,
        lag(gil_earned) over lease_observations as previous_gil_earned
    from {{ ref('silver_state_snapshots') }}
    window lease_observations as (
        partition by lease_id
        order by observed_at, event_id
    )
),
deltas as (
    select
        *,
        date_diff('second', previous_observed_at, observed_at) as observation_gap_seconds,
        elapsed_seconds - previous_elapsed_seconds as active_seconds_raw,
        exp_earned - previous_exp_earned as exp_earned_delta_raw,
        gil_earned - previous_gil_earned as gil_earned_delta_raw
    from ordered
),
assessed as (
    select
        *,
        case
            when lease_id is null
                or elapsed_seconds is null
                or exp_earned is null
                or gil_earned is null
                then 'unavailable'
            when previous_observed_at is null
                then 'baseline_only'
            when observation_gap_seconds <= 0
                then 'invalid_interval'
            when observation_gap_seconds > 300
                then 'observation_gap'
            when active_seconds_raw < 0
                or exp_earned_delta_raw < 0
                or gil_earned_delta_raw < 0
                then 'counter_reset'
            when active_seconds_raw = 0
                and exp_earned_delta_raw = 0
                and gil_earned_delta_raw = 0
                then 'idle_interval'
            when active_seconds_raw <= 0
                then 'inconsistent_counter'
            else 'observed_delta'
        end as metric_quality
    from deltas
)
select
    event_id,
    observed_at,
    observation_date,
    agent_id,
    lease_id,
    active_zone_id,
    phase,
    status,
    source_git_sha,
    git_sha_provenance,
    previous_observed_at,
    observation_gap_seconds,
    elapsed_seconds,
    exp_earned as lease_exp_earned,
    gil_earned as lease_gil_earned,
    case
        when elapsed_seconds > 0 then exp_earned * 3600.0 / elapsed_seconds
        else null
    end as lease_exp_per_active_hour,
    case
        when elapsed_seconds > 0 then gil_earned * 3600.0 / elapsed_seconds
        else null
    end as lease_gil_per_active_hour,
    case when metric_quality = 'observed_delta' then active_seconds_raw end
        as active_seconds,
    case when metric_quality = 'observed_delta' then exp_earned_delta_raw end
        as exp_earned_delta,
    case when metric_quality = 'observed_delta' then gil_earned_delta_raw end
        as gil_earned_delta,
    case
        when metric_quality = 'observed_delta' and active_seconds_raw > 0
            then exp_earned_delta_raw * 3600.0 / active_seconds_raw
        else null
    end as exp_per_active_hour,
    case
        when metric_quality = 'observed_delta' and active_seconds_raw > 0
            then gil_earned_delta_raw * 3600.0 / active_seconds_raw
        else null
    end as gil_per_active_hour,
    metric_quality
from assessed
