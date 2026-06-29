{{ config(materialized='table', schema='mart') }}

select
    'course_context__event_context' as review_flag_id,
    'course_context' as review_family,
    'event_context_flag' as review_flag_name,
    'A nominal hard split pattern clusters at the event-leg level.' as review_flag_description,
    'The event leg may differ from nominal distance or conditions.' as review_flag_interpretation,
    'This is a course or timing context signal, not an athlete accusation.' as review_flag_caveat
union all
select
    'nominal__nominal_hard',
    'nominal',
    'nominal_hard_flag',
    'At least one split implies a speed outside conservative nominal thresholds.',
    'The row deserves review against course and timing context.',
    'Nominal assumptions can be wrong for shortened, altered, or unusual courses.'
union all
select
    'individual_profile__individual_hard',
    'individual_profile',
    'individual_hard_flag',
    'A nominal hard split is not explained by an event-context cluster.',
    'The individual profile is unusual under nominal assumptions.',
    'This is a review signal only and should be interpreted with event notes.'
union all
select
    'record_integrity__record_integrity',
    'record_integrity',
    'record_integrity_flag',
    'One or more timing fields do not reconcile cleanly.',
    'The row may have timing, split, or transition data issues.',
    'Record-integrity issues can come from source system formatting or timing mats.'
union all
select
    'record_integrity__reconciliation',
    'record_integrity',
    'reconciliation_flag',
    'Overall time differs from split plus transition time beyond the configured limit.',
    'The row may need timing reconciliation.',
    'Small differences can be normal depending on official timing conventions.'
union all
select
    'record_integrity__duplicate_split_overall',
    'record_integrity',
    'duplicate_split_overall_flag',
    'A split or transition value equals the overall time.',
    'A timing field may have been copied into the wrong column.',
    'Some source exports can use placeholder values for missing splits.'
union all
select
    'record_integrity__extreme_transition',
    'record_integrity',
    'extreme_transition_flag',
    'Combined transition time exceeds the configured review threshold.',
    'Transition timing may be missing, miscoded, or unusual.',
    'Extreme transitions can be legitimate in unusual race circumstances.'
union all
select
    'rank_audit__rank_audit',
    'rank_audit',
    'rank_audit_flag',
    'A finisher has missing or non-positive rank fields.',
    'The row may need rank-field review.',
    'Rank fields are secondary to timing fields for analytical validity.'
union all
select
    'individual_profile__consistency',
    'individual_profile',
    'consistency_flag',
    'Within-event split percentiles have a large spread.',
    'The split profile is unusually inconsistent relative to peers.',
    'This can reflect athlete strengths, course effects, pacing, or data issues.'
union all
select
    'model_residual__model_residual',
    'model_residual',
    'model_residual_flag',
    'Placeholder for future notebook/model residual review signals.',
    'No residual model is active in the initial dbt implementation.',
    'Residual flags, if added later, remain review signals only.'
