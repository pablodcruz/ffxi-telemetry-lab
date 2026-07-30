select
    event_id,
    event_time,
    cast(event_time as date) as event_date,
    ingested_at,
    agent_id,
    lease_id,
    event_type,
    json_extract_string(raw_json, '$.mode') as engagement_mode,
    json_extract_string(raw_json, '$.phase') as phase,
    json_extract_string(raw_json, '$.name') as target_or_action_name,
    json_extract_string(raw_json, '$.reason') as reason,
    json_extract_string(raw_json, '$.status') as status,
    try_cast(json_extract_string(raw_json, '$.fight') as bigint) as fight_number,
    try_cast(json_extract_string(raw_json, '$.zone_id') as integer) as zone_id,
    try_cast(json_extract_string(raw_json, '$.from_zone_id') as integer) as from_zone_id,
    try_cast(json_extract_string(raw_json, '$.to_zone_id') as integer) as to_zone_id,
    try_cast(json_extract_string(raw_json, '$.target_level') as integer) as target_level,
    try_cast(json_extract_string(raw_json, '$.level') as integer) as reached_level,
    try_cast(json_extract_string(raw_json, '$.player_hp_percent') as double)
        as player_hp_percent,
    try_cast(json_extract_string(raw_json, '$.aggro_response_ms') as double)
        as aggro_response_ms,
    try_cast(json_extract_string(raw_json, '$.handoff_queue_ms') as double)
        as handoff_queue_ms,
    coalesce(try_cast(json_extract_string(raw_json, '$.handoff') as boolean), false)
        as was_handoff,
    source_file,
    source_line_number,
    source_git_sha,
    git_sha_provenance,
    schema_version,
    raw_json
from {{ source('bronze', 'bronze_events') }}
where source = 'farm_supervisor'
