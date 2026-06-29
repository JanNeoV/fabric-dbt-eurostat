select
    source_file_name,
    source_row_number
from {{ ref('src_coachcox_results_raw') }}
where nullif(trim(cast(source_seed_name as varchar(512))), '') is null
    or nullif(trim(cast(source_file_name as varchar(512))), '') is null
    or try_cast(source_row_number as int) is null
    or try_cast(source_row_number as int) <= 0
    or nullif(trim(cast(event_id as varchar(128))), '') is null
    or nullif(trim(cast(race_slug as varchar(512))), '') is null
    or nullif(trim(cast(race_name as varchar(512))), '') is null
    or try_cast(year as int) is null
    or distance not in ('70.3', 'full', 'unknown')
