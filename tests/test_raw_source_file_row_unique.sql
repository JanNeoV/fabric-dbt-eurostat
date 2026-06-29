select
    source_file_name,
    source_row_number,
    count(*) as duplicate_rows
from {{ ref('src_coachcox_results_raw') }}
group by source_file_name, source_row_number
having count(*) > 1
