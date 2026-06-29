{{ config(materialized='table', schema='mart') }}

with review_flags as (
    select *
    from {{ ref('int_review_flags') }}
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
    review_flags.result_id,
    review_flags.event_id,
    dim_division.division_id,
    dim_gender.gender_id,
    dim_distance.distance_id,
    review_flags.finish_status,
    review_flags.overall_seconds,
    review_flags.swim_seconds,
    review_flags.bike_seconds,
    review_flags.run_seconds,
    review_flags.t1_seconds,
    review_flags.t2_seconds,
    review_flags.swim_rel,
    review_flags.bike_rel,
    review_flags.run_rel,
    review_flags.overall_rel,
    review_flags.consistency_spread_rel,
    review_flags.is_finisher,
    review_flags.is_valid_sbr_finisher,
    review_flags.event_context_flag,
    review_flags.record_integrity_flag,
    review_flags.individual_profile_flag,
    review_flags.individual_hard_flag,
    review_flags.model_residual_flag,
    review_flags.any_review_flag,
    review_flags.flag_layer_count
from review_flags
left join dim_division
    on coalesce(review_flags.division, 'Unknown') = dim_division.division
left join dim_gender
    on coalesce(review_flags.gender, 'Unknown') = dim_gender.gender
left join dim_distance
    on coalesce(review_flags.distance_raw, 'unknown') = dim_distance.distance
