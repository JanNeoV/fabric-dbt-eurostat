select result_id
from {{ ref('int_result_times') }}
where is_valid_sbr_finisher = 1
    and (
        swim_seconds is null
        or bike_seconds is null
        or run_seconds is null
        or is_finisher <> 1
        or has_valid_gender <> 1
    )
