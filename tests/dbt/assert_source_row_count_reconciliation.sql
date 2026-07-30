select *
from {{ source('bronze', 'ingestion_source_reconciliation') }}
where lines_read <> valid_json_rows + malformed_rows
   or valid_json_rows <> new_rows + duplicate_rows
