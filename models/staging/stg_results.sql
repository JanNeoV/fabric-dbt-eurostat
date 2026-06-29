{{ config(materialized='table', schema='staging') }}

with raw_results as (
    select *
    from {{ ref('src_coachcox_results_raw') }}
),

renamed as (
    select
        raw_results.source_seed_name,
        raw_results.source_file_name,
        raw_results.source_row_number,
        raw_results.event_id,
        raw_results.race_name,
        raw_results.year,
        raw_results.distance as distance_raw,
        case
            when upper(trim(cast(raw_results.gender as varchar(64)))) in ('M', 'MALE') then 'Male'
            when upper(trim(cast(raw_results.gender as varchar(64)))) in ('F', 'FEMALE') then 'Female'
            else nullif(trim(cast(raw_results.gender as varchar(64))), '')
        end as gender,
        nullif(trim(cast(raw_results.division as varchar(64))), '') as division,
        upper(nullif(trim(cast(raw_results.finish as varchar(32))), '')) as finish_status,
        nullif(trim(cast(raw_results.name as varchar(512))), '') as name_raw,
        nullif(trim(cast(raw_results.bib as varchar(128))), '') as bib_raw,
        nullif(trim(cast(raw_results.country as varchar(128))), '') as country_raw,
        nullif(trim(cast(raw_results.overall_time as varchar(64))), '') as overall_time_raw,
        nullif(trim(cast(raw_results.swim_time as varchar(64))), '') as swim_time_raw,
        nullif(trim(cast(raw_results.bike_time as varchar(64))), '') as bike_time_raw,
        nullif(trim(cast(raw_results.run_time as varchar(64))), '') as run_time_raw,
        nullif(trim(cast(raw_results.transition_1_time as varchar(64))), '') as t1_time_raw,
        nullif(trim(cast(raw_results.transition_2_time as varchar(64))), '') as t2_time_raw,
        try_cast(nullif(trim(cast(raw_results.overall_rank as varchar(64))), '') as int) as overall_rank_raw,
        try_cast(nullif(trim(cast(raw_results.gender_rank as varchar(64))), '') as int) as gender_rank_raw,
        try_cast(nullif(trim(cast(raw_results.age_group_rank as varchar(64))), '') as int) as division_rank_raw,
        nullif(trim(cast(raw_results.qualifier_time as varchar(64))), '') as qualifier_time_raw,
        try_cast(nullif(trim(cast(raw_results.qualifier_rank as varchar(64))), '') as int) as qualifier_rank_raw,
        try_cast(nullif(trim(cast(raw_results.gender_qualifier_rank as varchar(64))), '') as int) as gender_qualifier_rank_raw,
        try_cast(nullif(trim(cast(raw_results.qualified as varchar(64))), '') as int) as is_qualifier_raw
    from raw_results
)

select
    {{ generate_surrogate_key([
        'source_file_name',
        'source_row_number'
    ]) }} as result_id,
    source_seed_name,
    source_file_name,
    source_row_number,
    event_id,
    race_name,
    year,
    distance_raw,
    gender,
    division,
    finish_status,
    name_raw,
    bib_raw,
    country_raw,
    overall_time_raw,
    swim_time_raw,
    bike_time_raw,
    run_time_raw,
    t1_time_raw,
    t2_time_raw,
    overall_rank_raw,
    gender_rank_raw,
    division_rank_raw,
    qualifier_time_raw,
    qualifier_rank_raw,
    gender_qualifier_rank_raw,
    is_qualifier_raw
from renamed
