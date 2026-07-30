select
    event_date,
    operation,
    source_git_sha,
    git_sha_provenance,
    count(*) as operation_count,
    count_if(outcome = 'ok') as successful_operations,
    count_if(outcome = 'error') as failed_operations,
    count_if(outcome = 'ok')::double / nullif(count(*), 0) as success_rate,
    quantile_cont(duration_ms, 0.50) filter (where duration_ms is not null)
        as duration_p50_ms,
    quantile_cont(duration_ms, 0.95) filter (where duration_ms is not null)
        as duration_p95_ms,
    max(duration_ms) as duration_max_ms
from {{ ref('silver_agent_actions') }}
group by event_date, operation, source_git_sha, git_sha_provenance
