select result_id
from {{ ref('int_result_times') }}
where coalesce(overall_seconds, 1) <= 0
    or coalesce(swim_seconds, 1) <= 0
    or coalesce(bike_seconds, 1) <= 0
    or coalesce(run_seconds, 1) <= 0
    or coalesce(t1_seconds, 1) <= 0
    or coalesce(t2_seconds, 1) <= 0
