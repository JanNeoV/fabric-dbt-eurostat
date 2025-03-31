SELECT 
    {{ generate_tsql_surrogate_key_integer(["dimension_code"], 3) }} AS pk
    , dimension_code as unit_code
    , dimension_label as unit_label
FROM [LH_EUROSTAT].[PublicFinance].[dim_unit]