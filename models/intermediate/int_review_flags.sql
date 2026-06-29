{{ config(materialized='table', schema='intermediate') }}

with result_percentiles as (
    select *
    from {{ ref('int_result_percentiles') }}
),

event_leg_context as (
    select *
    from {{ ref('int_event_leg_context') }}
),

result_legs as (
    select
        result_id,
        event_id,
        gender,
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
        result_id,
        event_id,
        gender,
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
        result_id,
        event_id,
        gender,
        'run' as leg,
        run_seconds as leg_seconds,
        case
            when distance_raw = '70.3' then 21.1
            when distance_raw = 'full' then 42.2
        end as nominal_km
    from result_percentiles
    where is_finisher = 1 and has_valid_gender = 1
),

result_leg_flags as (
    select
        result_legs.*,
        cast(result_legs.nominal_km * 3600.0 / nullif(result_legs.leg_seconds, 0) as float) as speed_kmh,
        cast(case
            when result_legs.leg_seconds is null or result_legs.nominal_km is null then 0
            when result_legs.leg = 'swim'
                and (
                    (result_legs.nominal_km * 3600.0 / nullif(result_legs.leg_seconds, 0)) < {{ var('swim_min_kmh') }}
                    or (result_legs.nominal_km * 3600.0 / nullif(result_legs.leg_seconds, 0)) > {{ var('swim_max_kmh') }}
                ) then 1
            when result_legs.leg = 'bike'
                and (
                    (result_legs.nominal_km * 3600.0 / nullif(result_legs.leg_seconds, 0)) < {{ var('bike_min_kmh') }}
                    or (result_legs.nominal_km * 3600.0 / nullif(result_legs.leg_seconds, 0)) > {{ var('bike_max_kmh') }}
                ) then 1
            when result_legs.leg = 'run'
                and (
                    (result_legs.nominal_km * 3600.0 / nullif(result_legs.leg_seconds, 0)) < {{ var('run_min_kmh') }}
                    or (result_legs.nominal_km * 3600.0 / nullif(result_legs.leg_seconds, 0)) > {{ var('run_max_kmh') }}
                ) then 1
            else 0
        end as int) as nominal_hard_leg_flag
    from result_legs
),

result_context as (
    select
        result_leg_flags.result_id,
        max(result_leg_flags.nominal_hard_leg_flag) as nominal_hard_flag_value,
        max(case
            when result_leg_flags.nominal_hard_leg_flag = 1
                and coalesce(cast(event_leg_context.event_context_flag as int), 0) = 1
            then 1 else 0
        end) as event_context_flag_value,
        max(case
            when result_leg_flags.nominal_hard_leg_flag = 1
            then result_leg_flags.speed_kmh
        end) as nominal_hard_evidence_value
    from result_leg_flags
    left join event_leg_context
        on result_leg_flags.event_id = event_leg_context.event_id
        and result_leg_flags.gender = event_leg_context.gender
        and result_leg_flags.leg = event_leg_context.leg
    group by result_leg_flags.result_id
),

base_flags as (
    select
        result_percentiles.*,
        cast(coalesce(result_context.nominal_hard_flag_value, 0) as bit) as nominal_hard_flag,
        cast(coalesce(result_context.event_context_flag_value, 0) as bit) as event_context_flag,
        result_context.nominal_hard_evidence_value,
        cast(case
            when result_percentiles.abs_reconciliation_delta_seconds > {{ var('reconciliation_limit_seconds') }}
            then 1 else 0
        end as bit) as reconciliation_flag,
        cast(case
            when result_percentiles.overall_seconds is not null
                and (
                    result_percentiles.swim_seconds = result_percentiles.overall_seconds
                    or result_percentiles.bike_seconds = result_percentiles.overall_seconds
                    or result_percentiles.run_seconds = result_percentiles.overall_seconds
                    or result_percentiles.t1_seconds = result_percentiles.overall_seconds
                    or result_percentiles.t2_seconds = result_percentiles.overall_seconds
                )
            then 1 else 0
        end as bit) as duplicate_split_overall_flag,
        cast(case
            when result_percentiles.transition_seconds > {{ var('extreme_transition_limit_seconds') }}
            then 1 else 0
        end as bit) as extreme_transition_flag,
        cast(case
            when result_percentiles.is_finisher = 1
                and (
                    result_percentiles.overall_rank_raw is null
                    or result_percentiles.gender_rank_raw is null
                    or result_percentiles.division_rank_raw is null
                    or result_percentiles.overall_rank_raw <= 0
                    or result_percentiles.gender_rank_raw <= 0
                    or result_percentiles.division_rank_raw <= 0
                )
            then 1 else 0
        end as bit) as rank_audit_flag,
        cast(case
            when result_percentiles.consistency_spread_rel >= {{ var('consistency_spread_threshold') }}
            then 1 else 0
        end as bit) as consistency_flag,
        cast(0 as bit) as model_residual_flag,
        cast(null as float) as model_residual_value
    from result_percentiles
    left join result_context
        on result_percentiles.result_id = result_context.result_id
),

combined as (
    select
        *,
        cast(case
            when reconciliation_flag = 1
                or duplicate_split_overall_flag = 1
                or extreme_transition_flag = 1
            then 1 else 0
        end as bit) as record_integrity_flag,
        cast(case
            when nominal_hard_flag = 1 and event_context_flag = 0
            then 1 else 0
        end as bit) as individual_hard_flag
    from base_flags
),

final_flags as (
    select
        *,
        cast(case
            when individual_hard_flag = 1 or consistency_flag = 1
            then 1 else 0
        end as bit) as individual_profile_flag
    from combined
)

select
    *,
    cast(case
        when nominal_hard_flag = 1
            or individual_hard_flag = 1
            or event_context_flag = 1
            or record_integrity_flag = 1
            or rank_audit_flag = 1
            or consistency_flag = 1
            or model_residual_flag = 1
        then 1 else 0
    end as bit) as any_review_flag,
    (
        case when event_context_flag = 1 then 1 else 0 end
        + case when record_integrity_flag = 1 then 1 else 0 end
        + case when individual_hard_flag = 1 then 1 else 0 end
        + case when rank_audit_flag = 1 then 1 else 0 end
        + case when consistency_flag = 1 then 1 else 0 end
        + case when model_residual_flag = 1 then 1 else 0 end
    ) as flag_layer_count
from final_flags
