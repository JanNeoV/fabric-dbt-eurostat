{{ config(materialized='table', schema='mart') }}

with divisions as (
    select 'Unknown' as division
    union
    select distinct division
    from {{ ref('int_review_flags') }}
    where division is not null
)

select
    {{ generate_surrogate_key(['division']) }} as division_id,
    division,
    cast(case
        when upper(division) like '%PRO%' or upper(division) in ('MPRO', 'FPRO', 'PRO')
        then 1 else 0
    end as bit) as is_pro,
    case
        when upper(division) in ('MPRO', 'FPRO', 'PRO') or upper(division) like '%PRO%' then 'Pro'
        when len(division) > 1 and left(upper(division), 1) in ('M', 'F') then substring(division, 2, len(division))
        else null
    end as age_group,
    case
        when left(upper(division), 1) = 'M' then 'Male'
        when left(upper(division), 1) = 'F' then 'Female'
    end as gender_default_if_parseable
from divisions
