with bronze_profile as (
    select
        source,
        count(*) as bronze_rows,
        count(distinct event_id) as distinct_event_ids,
        count_if(event_id is null) as null_event_ids,
        count_if(event_time is null) as null_event_times,
        count(*) - count(distinct event_id) as duplicate_event_ids,
        min(event_time) as earliest_event_time,
        max(event_time) as latest_event_time,
        max(ingested_at) as latest_ingested_at
    from {{ source('bronze', 'bronze_events') }}
    group by source
),
latest_sessions as (
    select *
    from {{ source('bronze', 'ingestion_source_reconciliation') }}
    qualify row_number() over (partition by source order by session_id desc) = 1
)
select
    coalesce(b.source, s.source) as source,
    coalesce(b.bronze_rows, 0) as bronze_rows,
    coalesce(b.distinct_event_ids, 0) as distinct_event_ids,
    coalesce(b.null_event_ids, 0) as null_event_ids,
    coalesce(b.null_event_times, 0) as null_event_times,
    coalesce(b.duplicate_event_ids, 0) as duplicate_event_ids,
    b.earliest_event_time,
    b.latest_event_time,
    b.latest_ingested_at,
    coalesce(s.lines_read, 0) as latest_session_lines_read,
    coalesce(s.valid_json_rows, 0) as latest_session_valid_rows,
    coalesce(s.malformed_rows, 0) as latest_session_malformed_rows,
    coalesce(s.new_rows, 0) as latest_session_new_rows,
    coalesce(s.duplicate_rows, 0) as latest_session_duplicate_rows,
    coalesce(s.lines_read, 0) = coalesce(s.valid_json_rows, 0)
        + coalesce(s.malformed_rows, 0) as latest_session_reconciled
from bronze_profile b
full outer join latest_sessions s using (source)
