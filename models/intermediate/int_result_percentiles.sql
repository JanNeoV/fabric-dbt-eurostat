{{ config(materialized='table', schema='intermediate') }}

with result_times as (
    select *
    from {{ ref('int_result_times') }}
),

valid_finishers as (
    select
        result_id,
        cast(1.0 - percent_rank() over (
            partition by event_id, gender
            order by swim_seconds asc
        ) as float) as swim_rel,
        cast(1.0 - percent_rank() over (
            partition by event_id, gender
            order by bike_seconds asc
        ) as float) as bike_rel,
        cast(1.0 - percent_rank() over (
            partition by event_id, gender
            order by run_seconds asc
        ) as float) as run_rel,
        cast(1.0 - percent_rank() over (
            partition by event_id, gender
            order by overall_seconds asc
        ) as float) as overall_rel
    from result_times
    where is_valid_sbr_finisher = 1
),

scored as (
    select
        result_times.*,
        valid_finishers.swim_rel,
        valid_finishers.bike_rel,
        valid_finishers.run_rel,
        valid_finishers.overall_rel
    from result_times
    left join valid_finishers
        on result_times.result_id = valid_finishers.result_id
)

select
    *,
    case
        when swim_rel is null or bike_rel is null or run_rel is null then null
        when swim_rel >= bike_rel and swim_rel >= run_rel then swim_rel
        when bike_rel >= swim_rel and bike_rel >= run_rel then bike_rel
        else run_rel
    end as best_leg_rel,
    case
        when swim_rel is null or bike_rel is null or run_rel is null then null
        when swim_rel <= bike_rel and swim_rel <= run_rel then swim_rel
        when bike_rel <= swim_rel and bike_rel <= run_rel then bike_rel
        else run_rel
    end as worst_leg_rel,
    case
        when swim_rel is null or bike_rel is null or run_rel is null then null
        else
            (
                case
                    when swim_rel >= bike_rel and swim_rel >= run_rel then swim_rel
                    when bike_rel >= swim_rel and bike_rel >= run_rel then bike_rel
                    else run_rel
                end
            )
            -
            (
                case
                    when swim_rel <= bike_rel and swim_rel <= run_rel then swim_rel
                    when bike_rel <= swim_rel and bike_rel <= run_rel then bike_rel
                    else run_rel
                end
            )
    end as consistency_spread_rel
from scored
