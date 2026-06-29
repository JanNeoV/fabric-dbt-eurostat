{{ config(materialized='table', schema='semantic') }}

with fct_result as (
    select *
    from {{ ref('fct_result') }}
),

dim_event as (
    select *
    from {{ ref('dim_event') }}
),

dim_division as (
    select *
    from {{ ref('dim_division') }}
),

dim_gender as (
    select *
    from {{ ref('dim_gender') }}
),

dim_distance as (
    select *
    from {{ ref('dim_distance') }}
)

select
    fct_result.result_id,
    fct_result.event_id,
    fct_result.division_id,
    fct_result.gender_id,
    fct_result.distance_id,
    dim_event.race_name,
    case
        when dim_event.year is not null
        then datefromparts(dim_event.year, 1, 1)
    end as event_year,
    dim_distance.distance,
    dim_gender.gender,
    dim_division.division,
    dim_division.is_pro,
    fct_result.finish_status,
    fct_result.is_finisher,
    fct_result.is_valid_sbr_finisher,
    fct_result.overall_seconds,
    fct_result.swim_seconds,
    fct_result.bike_seconds,
    fct_result.run_seconds,
    fct_result.swim_rel,
    fct_result.bike_rel,
    fct_result.run_rel,
    fct_result.overall_rel,
    fct_result.consistency_spread_rel,
    fct_result.any_review_flag,
    fct_result.event_context_flag,
    fct_result.record_integrity_flag,
    fct_result.individual_profile_flag,
    fct_result.model_residual_flag,
    fct_result.individual_hard_flag
from fct_result
left join dim_event
    on fct_result.event_id = dim_event.event_id
left join dim_division
    on fct_result.division_id = dim_division.division_id
left join dim_gender
    on fct_result.gender_id = dim_gender.gender_id
left join dim_distance
    on fct_result.distance_id = dim_distance.distance_id
