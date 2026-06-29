{{ config(materialized='table', schema='mart') }}

with genders as (
    select 'Unknown' as gender
    union
    select distinct gender
    from {{ ref('int_review_flags') }}
    where gender is not null
)

select
    {{ generate_surrogate_key(['gender']) }} as gender_id,
    gender
from genders
