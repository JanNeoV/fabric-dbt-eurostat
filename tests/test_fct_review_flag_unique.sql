select
    result_id,
    review_flag_id,
    count(*) as duplicate_rows
from {{ ref('fct_review_flag') }}
group by result_id, review_flag_id
having count(*) > 1
