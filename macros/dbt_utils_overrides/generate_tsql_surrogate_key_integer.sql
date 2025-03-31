{% macro generate_tsql_surrogate_key_integer(field_list, max_digits=9) -%}
    /*
      Generates a deterministic integer surrogate key by:
        1) Coalescing all fields to a string (with a delimiter).
        2) Hashing them using T-SQL's HASHBYTES (MD5, SHA1, or SHA2_256).
        3) Extracting 8 bytes and converting to BIGINT.
        4) Taking an ABS(...) and mod 10^<max_digits> to limit length.

      Example usage inside a SELECT:
        {{ generate_tsql_surrogate_key_integer(["country", "region"], 6) }} as country_surrogate_key
    */

    {%- set delimiter = '|' -%}
    {%- set default_null_value = '' -%}

    {%- set fields = [] -%}
    {%- for field in field_list -%}
      {%- do fields.append("COALESCE(" ~ field ~ ", '" ~ default_null_value ~ "')") -%}
    {%- endfor -%}

    -- E.g. COALESCE(field1, '') + '|' + COALESCE(field2, '') + '|' + ...
    {%- set combined_expression = fields | join(' + \'' ~ delimiter ~ '\' + ') -%}

    /*
      1) HASHBYTES('MD5', combined_expression) returns varbinary(16)
      2) SUBSTRING(..., 1, 8) grabs first 8 bytes -> varbinary(8)
      3) CAST(... as BIGINT) interprets those 8 bytes as a 64-bit integer
      4) ABS() ensures non-negative
      5) % POWER(10, max_digits) to reduce the final size
    */

    ABS(
        CAST(
            SUBSTRING(
                HASHBYTES('MD5', {{ combined_expression }} ),
                1,
                8
            ) AS BIGINT
        )
    ) % CAST(POWER(10, {{ max_digits }}) as BIGINT)

{%- endmacro %}
