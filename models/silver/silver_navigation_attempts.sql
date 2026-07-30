select
    event_id,
    event_time,
    cast(event_time as date) as event_date,
    agent_id,
    json_extract_string(raw_json, '$.outcome') as outcome,
    try_cast(json_extract_string(raw_json, '$.requested_distance') as double)
        as requested_distance,
    try_cast(json_extract_string(raw_json, '$.displacement') as double) as displacement,
    try_cast(json_extract_string(raw_json, '$.remaining') as double) as remaining_distance,
    try_cast(json_extract_string(raw_json, '$.hp_percent') as double) as hp_percent,
    json_extract_string(raw_json, '$.mesh') as mesh,
    source_file,
    source_line_number,
    source_git_sha,
    git_sha_provenance,
    raw_json
from {{ source('bronze', 'bronze_events') }}
where source = 'navigation'
