{{ config(materialized='table', schema='mart') }}

with event_leg_context as (
    select *
    from {{ ref('int_event_leg_context') }}
),

dim_gender as (
    select *
    from {{ ref('dim_gender') }}
)

select
    event_leg_context.event_id,
    dim_gender.gender_id,
    event_leg_context.leg,
    event_leg_context.valid_leg_rows,
    event_leg_context.nominal_hard_flag_rows,
    event_leg_context.event_nominal_hard_rate,
    event_leg_context.event_context_band,
    event_leg_context.event_context_flag
from event_leg_context
left join dim_gender
    on event_leg_context.gender = dim_gender.gender
