SELECT 
    {{ generate_tsql_surrogate_key_integer(["dimension_code"], 8) }} AS pk
    , dimension_code as country_code
    , dimension_label as country
 FROM [LH_EUROSTAT].[PublicFinance].[dim_geo]