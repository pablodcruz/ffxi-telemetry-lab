select
    event_id,
    event_time as observed_at,
    cast(event_time as date) as observation_date,
    agent_id,
    lease_id,
    json_extract_string(raw_json, '$.phase') as phase,
    json_extract_string(raw_json, '$.status') as status,
    try_cast(json_extract_string(raw_json, '$.active_zone_id') as integer) as active_zone_id,
    json_extract_string(raw_json, '$.current_target.name') as current_target_name,
    json_extract_string(raw_json, '$.configuration_hash') as configuration_hash,
    try_cast(json_extract_string(raw_json, '$.elapsed_seconds') as bigint) as elapsed_seconds,
    try_cast(json_extract_string(raw_json, '$.counters.exp_earned') as bigint) as exp_earned,
    try_cast(json_extract_string(raw_json, '$.counters.gil_earned') as bigint) as gil_earned,
    try_cast(json_extract_string(raw_json, '$.counters.fights_completed') as bigint)
        as fights_completed,
    try_cast(json_extract_string(raw_json, '$.counters.deaths') as bigint) as deaths,
    try_cast(json_extract_string(raw_json, '$.counters.recoveries') as bigint) as recoveries,
    try_cast(json_extract_string(raw_json, '$.counters.proactive_engagements') as bigint)
        as proactive_engagements,
    try_cast(json_extract_string(raw_json, '$.counters.reactive_engagements') as bigint)
        as reactive_engagements,
    try_cast(json_extract_string(raw_json, '$.counters.attack_rejections') as bigint)
        as attack_rejections,
    try_cast(json_extract_string(raw_json, '$.counters.target_cycle_errors') as bigint)
        as target_cycle_errors,
    try_cast(json_extract_string(raw_json, '$.counters.teleport_while_engaged') as bigint)
        as teleport_while_engaged,
    try_cast(json_extract_string(raw_json, '$.counters.zone_transitions') as bigint)
        as zone_transitions,
    try_cast(json_extract_string(raw_json, '$.metrics.maximum_aggro_response_ms') as double)
        as maximum_aggro_response_ms,
    try_cast(json_extract_string(raw_json, '$.metrics.maximum_handoff_queue_ms') as double)
        as maximum_handoff_queue_ms,
    source_git_sha,
    git_sha_provenance,
    raw_json
from {{ source('bronze', 'bronze_events') }}
where source = 'state_snapshot'
