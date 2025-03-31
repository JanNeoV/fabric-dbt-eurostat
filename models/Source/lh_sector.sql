SELECT 
    {{ generate_tsql_surrogate_key_integer(["dimension_code"], 3) }} AS pk
    , dimension_code as sector_code
    , dimension_label as sector_label
FROM [LH_EUROSTAT].[PublicFinance].[dim_sector]