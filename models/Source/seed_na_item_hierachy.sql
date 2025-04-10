    SELECT
          LEVEL_1
          , LEVEL_1_DESCRIPTION
          , LEVEL_2
          , LEVEL_2_DESCRIPTION
          , LEVEL_3
          , LEVEL_3_DESCRIPTION
          , COALESCE(LEVEL_3, LEVEL_2, LEVEL_1) as helper_mapping
        , {{ generate_tsql_surrogate_key_integer(["COALESCE(LEVEL_3, LEVEL_2, LEVEL_1)"], 8) }} AS pk
    FROM
        {{ ref('na_items_mapping') }}