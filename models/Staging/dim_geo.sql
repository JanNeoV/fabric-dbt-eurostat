SELECT 
    pk
    , country_code
    , country
 FROM {{ ref('lh_geo') }}