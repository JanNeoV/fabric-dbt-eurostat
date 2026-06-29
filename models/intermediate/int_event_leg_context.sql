{{ config(materialized='table', schema='intermediate') }}

with result_percentiles as (
    select *
    from {{ ref('int_result_percentiles') }}
),

legs as (
    select
        event_id,
        gender,
        distance_raw as distance,
        'swim' as leg,
        swim_seconds as leg_seconds,
        case
            when distance_raw = '70.3' then 1.9
            when distance_raw = 'full' then 3.8
        end as nominal_km
    from result_percentiles
    where is_finisher = 1 and has_valid_gender = 1

    union all

    select
        event_id,
        gender,
        distance_raw as distance,
        'bike' as leg,
        bike_seconds as leg_seconds,
        case
            when distance_raw = '70.3' then 90.0
            when distance_raw = 'full' then 180.0
        end as nominal_km
    from result_percentiles
    where is_finisher = 1 and has_valid_gender = 1

    union all

    select
        event_id,
        gender,
        distance_raw as distance,
        'run' as leg,
        run_seconds as leg_seconds,
        case
            when distance_raw = '70.3' then 21.1
            when distance_raw = 'full' then 42.2
        end as nominal_km
    from result_percentiles
    where is_finisher = 1 and has_valid_gender = 1
),

leg_speeds as (
    select
        *,
        cast(nominal_km * 3600.0 / nullif(leg_seconds, 0) as float) as speed_kmh
    from legs
    where leg_seconds is not null
        and leg_seconds > 0
        and nominal_km is not null
),

leg_flags as (
    select
        *,
        cast(case
            when leg = 'swim' and (speed_kmh < {{ var('swim_min_kmh') }} or speed_kmh > {{ var('swim_max_kmh') }}) then 1
            when leg = 'bike' and (speed_kmh < {{ var('bike_min_kmh') }} or speed_kmh > {{ var('bike_max_kmh') }}) then 1
            when leg = 'run' and (speed_kmh < {{ var('run_min_kmh') }} or speed_kmh > {{ var('run_max_kmh') }}) then 1
            else 0
        end as int) as nominal_hard_flag
    from leg_speeds
),

aggregated as (
    select
        event_id,
        gender,
        leg,
        count(*) as valid_leg_rows,
        sum(nominal_hard_flag) as nominal_hard_flag_rows,
        cast(sum(nominal_hard_flag) as float) / nullif(count(*), 0) as event_nominal_hard_rate
    from leg_flags
    group by event_id, gender, leg
)

select
    event_id,
    gender,
    leg,
    valid_leg_rows,
    nominal_hard_flag_rows,
    event_nominal_hard_rate,
    case
        when event_nominal_hard_rate < 0.05 then 'normal_tail'
        when event_nominal_hard_rate >= 0.05 and event_nominal_hard_rate < 0.20 then 'ambiguous_review_zone'
        when event_nominal_hard_rate >= 0.20 and event_nominal_hard_rate < 0.80 then 'likely_event_context'
        when event_nominal_hard_rate >= 0.80 then 'probable_event_context'
    end as event_context_band,
    cast(case
        when event_nominal_hard_rate >= {{ var('possible_context_hard_rate') }} then 1
        else 0
    end as bit) as event_context_flag
from aggregated
