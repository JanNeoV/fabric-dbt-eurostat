select result_id
from {{ ref('int_result_percentiles') }}
where (swim_rel is not null and (swim_rel < 0 or swim_rel > 1))
    or (bike_rel is not null and (bike_rel < 0 or bike_rel > 1))
    or (run_rel is not null and (run_rel < 0 or run_rel > 1))
    or (overall_rel is not null and (overall_rel < 0 or overall_rel > 1))
