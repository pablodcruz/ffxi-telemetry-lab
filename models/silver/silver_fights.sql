select
    event_id,
    event_time,
    event_date,
    lease_id,
    fight_number,
    target_or_action_name as target_name,
    player_hp_percent,
    source_git_sha,
    git_sha_provenance
from {{ ref('silver_supervisor_events') }}
where event_type = 'fight_complete'
