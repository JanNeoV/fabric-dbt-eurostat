SELECT 
    pk
    , document_date
    , current_value
    , {{ generate_tsql_surrogate_key_integer(["unit"], 3) }} AS fk_unit 
    , {{ generate_tsql_surrogate_key_integer(["sector"], 3) }} AS fk_sector 
    , {{ generate_tsql_surrogate_key_integer(["na_item"], 8) }} AS fk_national_accounts
    , {{ generate_tsql_surrogate_key_integer(["geo"], 8) }} AS fk_geo 
FROM {{ ref('lh_gov_10a_main') }}
WHERE na_item IN (
    'P131',
    'P12',
    'P11',
    'D11PAY',
    'D12PAY',
    'D2',
    'D99REC',
    'D99PAY',
    'D92REC',
    'D92PAY',
    'D91REC',
    'D76REC',
    'D76PAY',
    'D75REC',
    'D75PAY',
    'D74REC',
    'D74PAY',
    'D73REC',
    'D73PAY',
    'D72REC',
    'D72PAY',
    'D71REC',
    'D71PAY',
    'D61REC',
    'D5PAY',
    'D41REC',
    'D42REC',
    'D43REC',
    'D44REC',
    'D45REC',
    'D4PAY',
    'D39PAY',
    'D31PAY',
    'D29REC',
    'D21REC',
    'D8',
    'D62_D632PAY',
    'D5REC',
    'D39REC',
    'OP5ANP',
    'P2',
    'D29PAY'
)
