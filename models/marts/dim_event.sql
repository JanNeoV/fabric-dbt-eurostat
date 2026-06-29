{{ config(materialized='table', schema='mart') }}

with result_events as (
    select
        event_id,
        max(race_name) as race_name,
        max(year) as year,
        max(distance_raw) as distance,
        max(source_file_name) as source_file_name
    from {{ ref('int_review_flags') }}
    group by event_id
),

event_context as (
    select
        event_id,
        max(cast(event_context_flag as int)) as event_has_context_flag_value
    from {{ ref('int_event_leg_context') }}
    group by event_id
)

select
    result_events.event_id,
    result_events.race_name,
    result_events.year,
    result_events.distance,
    result_events.source_file_name,
    case
        when result_events.distance = '70.3' then cast(1.9 as float)
        when result_events.distance = 'full' then cast(3.8 as float)
    end as nominal_swim_km,
    case
        when result_events.distance = '70.3' then cast(90.0 as float)
        when result_events.distance = 'full' then cast(180.0 as float)
    end as nominal_bike_km,
    case
        when result_events.distance = '70.3' then cast(21.1 as float)
        when result_events.distance = 'full' then cast(42.2 as float)
    end as nominal_run_km,
    cast(coalesce(event_context.event_has_context_flag_value, 0) as bit) as event_has_context_flag
from result_events
left join event_context
    on result_events.event_id = event_context.event_id
