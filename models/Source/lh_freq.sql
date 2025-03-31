SELECT 
    {{ generate_tsql_surrogate_key_integer(["dimension_code"], 8) }} AS pk
    , dimension_code
    , dimension_label

 FROM [LH_EUROSTAT].[PublicFinance].[dim_freq]