SELECT
    pk
    , LEVEL_1_DESCRIPTION
    , LEVEL_2_DESCRIPTION
    , LEVEL_3_DESCRIPTION   
FROM {{ ref('seed_na_item_hierachy') }}