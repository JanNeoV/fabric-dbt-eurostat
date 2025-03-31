SELECT 
    {{ generate_tsql_surrogate_key_integer(["dimension_code"], 1) }} AS pk
    , dimension_code as freq_code
    , dimension_label as interval

 FROM [LH_EUROSTAT].[PublicFinance].[dim_freq]