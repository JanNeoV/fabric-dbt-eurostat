SELECT 
    {{ generate_tsql_surrogate_key_integer(["dimension_code"], 10) }} AS pk
    , dimension_code as na_code
    , dimension_label as na_label
 FROM [LH_Eurostat].[PublicFinance].[dim_na_item]