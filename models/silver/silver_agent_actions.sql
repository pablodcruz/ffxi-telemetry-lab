select
    event_id,
    event_time,
    cast(event_time as date) as event_date,
    ingested_at,
    agent_id,
    event_type as operation,
    json_extract_string(raw_json, '$.outcome') as outcome,
    try_cast(json_extract_string(raw_json, '$.duration_ms') as double) as duration_ms,
    json_extract_string(raw_json, '$.error_code') as error_code,
    source_file,
    source_line_number,
    source_git_sha,
    git_sha_provenance,
    schema_version,
    raw_json
from {{ source('bronze', 'bronze_events') }}
where source = 'agent_actions'
