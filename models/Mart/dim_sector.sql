SELECT 
    pk
    , sector_code
    , sector_label
 FROM {{ ref('lh_sector') }}