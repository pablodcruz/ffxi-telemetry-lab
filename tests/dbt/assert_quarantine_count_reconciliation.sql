with source_counts as (
    select session_id, sum(malformed_rows) as malformed_rows
    from {{ source('bronze', 'ingestion_source_reconciliation') }}
    group by session_id
)
select s.session_id, s.quarantined_rows, c.malformed_rows
from {{ source('bronze', 'ingestion_sessions') }} s
join source_counts c using (session_id)
where s.quarantined_rows <> c.malformed_rows
