{{ config(materialized='table', schema='mart') }}

with review_flags as (
    select *
    from {{ ref('int_review_flags') }}
),

result_keys as (
    select
        review_flags.result_id,
        review_flags.event_id,
        dim_gender.gender_id,
        dim_division.division_id
    from review_flags
    left join {{ ref('dim_gender') }} as dim_gender
        on coalesce(review_flags.gender, 'Unknown') = dim_gender.gender
    left join {{ ref('dim_division') }} as dim_division
        on coalesce(review_flags.division, 'Unknown') = dim_division.division
),

flag_rows as (
    select result_id, 'course_context__event_context' as review_flag_id, cast(event_context_flag as int) as flag_value, nominal_hard_evidence_value as flag_evidence_value from review_flags
    union all
    select result_id, 'nominal__nominal_hard', cast(nominal_hard_flag as int), nominal_hard_evidence_value from review_flags
    union all
    select result_id, 'individual_profile__individual_hard', cast(individual_hard_flag as int), nominal_hard_evidence_value from review_flags
    union all
    select result_id, 'record_integrity__record_integrity', cast(record_integrity_flag as int), abs_reconciliation_delta_seconds from review_flags
    union all
    select result_id, 'record_integrity__reconciliation', cast(reconciliation_flag as int), abs_reconciliation_delta_seconds from review_flags
    union all
    select result_id, 'record_integrity__duplicate_split_overall', cast(duplicate_split_overall_flag as int), overall_seconds from review_flags
    union all
    select result_id, 'record_integrity__extreme_transition', cast(extreme_transition_flag as int), transition_seconds from review_flags
    union all
    select result_id, 'rank_audit__rank_audit', cast(rank_audit_flag as int), overall_rank_raw from review_flags
    union all
    select result_id, 'individual_profile__consistency', cast(consistency_flag as int), consistency_spread_rel from review_flags
    union all
    select result_id, 'model_residual__model_residual', cast(model_residual_flag as int), model_residual_value from review_flags
)

select
    flag_rows.result_id,
    flag_rows.review_flag_id,
    result_keys.event_id,
    result_keys.gender_id,
    result_keys.division_id,
    cast(flag_rows.flag_value as bit) as flag_value,
    cast(flag_rows.flag_evidence_value as float) as flag_evidence_value
from flag_rows
inner join result_keys
    on flag_rows.result_id = result_keys.result_id
where flag_rows.flag_value = 1
