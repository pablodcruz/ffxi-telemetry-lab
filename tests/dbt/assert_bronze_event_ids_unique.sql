select event_id
from {{ source('bronze', 'bronze_events') }}
group by event_id
having count(*) > 1 or event_id is null
