with cases as (
    select cast('1:02:03' as varchar(64)) as raw_time, cast(3723 as int) as expected_seconds
    union all
    select cast('59:30' as varchar(64)), cast(3570 as int)
    union all
    select cast('00:00:00' as varchar(64)), cast(null as int)
    union all
    select cast('' as varchar(64)), cast(null as int)
    union all
    select cast('bad' as varchar(64)), cast(null as int)
    union all
    select cast('-1:00' as varchar(64)), cast(null as int)
),

parsed as (
    select
        raw_time,
        expected_seconds,
        {{ parse_triathlon_time_to_seconds('raw_time') }} as actual_seconds
    from cases
)

select *
from parsed
where (expected_seconds is null and actual_seconds is not null)
    or (expected_seconds is not null and actual_seconds is null)
    or expected_seconds <> actual_seconds
