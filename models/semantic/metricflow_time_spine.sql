{{ config(materialized='table', schema='semantic') }}

with dim_event as (
    select *
    from {{ ref('dim_event') }}
),

bounds as (
    select
        datefromparts(coalesce(min(year), 2000), 1, 1) as start_date,
        datefromparts(coalesce(max(year), 2030), 12, 31) as end_date
    from dim_event
),

digits as (
    select 0 as n union all
    select 1 union all
    select 2 union all
    select 3 union all
    select 4 union all
    select 5 union all
    select 6 union all
    select 7 union all
    select 8 union all
    select 9
),

numbers as (
    select
        ones.n
        + tens.n * 10
        + hundreds.n * 100
        + thousands.n * 1000
        + ten_thousands.n * 10000 as day_offset
    from digits as ones
    cross join digits as tens
    cross join digits as hundreds
    cross join digits as thousands
    cross join digits as ten_thousands
)

select
    dateadd(day, numbers.day_offset, bounds.start_date) as date_day
from bounds
cross join numbers
where numbers.day_offset <= datediff(day, bounds.start_date, bounds.end_date)
