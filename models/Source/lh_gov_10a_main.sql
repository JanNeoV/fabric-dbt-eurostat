SELECT 
    {{ generate_tsql_surrogate_key_integer(
        ["na_item", "geo", "time", "value", "unit"], 20) }} AS pk
    , freq
    , unit
    , sector
    , na_item
    , geo
    , CAST(time AS INTEGER) as document_date
    , CAST(value AS BIGINT) as current_value
 FROM [LH_Eurostat].[PublicFinance].[gov_10a_main]
 WHERE value IS NOT NULL