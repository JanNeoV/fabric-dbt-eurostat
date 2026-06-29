{{ config(materialized='table', schema='mart') }}

select
    '70.3' as distance_id,
    '70.3' as distance,
    cast(1.9 as float) as nominal_swim_km,
    cast(90.0 as float) as nominal_bike_km,
    cast(21.1 as float) as nominal_run_km
union all
select
    'full',
    'full',
    cast(3.8 as float),
    cast(180.0 as float),
    cast(42.2 as float)
union all
select
    'unknown',
    'unknown',
    cast(null as float),
    cast(null as float),
    cast(null as float)
