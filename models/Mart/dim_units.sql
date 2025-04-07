SELECT 
    pk
    , unit_code
    , unit_label
FROM {{ ref('lh_unit') }}