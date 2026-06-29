select
    event_id,
    gender_id,
    leg,
    count(*) as duplicate_rows
from {{ ref('fct_event_leg_context') }}
group by event_id, gender_id, leg
having count(*) > 1
