SELECT 
    pk
    , document_date
    , current_value
    , {{ generate_tsql_surrogate_key_integer(["unit"], 3) }} AS fk_unit 
    , {{ generate_tsql_surrogate_key_integer(["sector"], 3) }} AS fk_sector 
    , {{ generate_tsql_surrogate_key_integer(["na_item"], 3) }} AS fk_national_accounts
    , {{ generate_tsql_surrogate_key_integer(["geo"], 3) }} AS fk_geo 
FROM {{ ref('lh_gov_10a_main') }}