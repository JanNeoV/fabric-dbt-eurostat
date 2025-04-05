{% macro generate_tsql_surrogate_key_integer(field_list, max_digits=9) %}
{# 
  Creates a deterministic integer (up to max_digits) by:
   1) Coalescing fields to '' and joining with '|'.
   2) Hashing via HASHBYTES('MD5', ...).
   3) Taking the first 8 bytes => BIGINT.
   4) Handling the minimum BIGINT value to avoid ABS() overflow.
   5) Taking the absolute value and modulo.
#}

{% set default_null_value = '' %}
{% set delimiter = '|' %}

{% set expression_parts = [] %}
{% for field in field_list %}
    {% do expression_parts.append("COALESCE(CAST(" ~ field ~ " AS CHAR), '" ~ default_null_value ~ "')") %}
{% endfor %}

{% set combined_expression = expression_parts | join(" + '" ~ delimiter ~ "' + ") %}

CASE 
    WHEN CAST(SUBSTRING(HASHBYTES('MD5', {{ combined_expression }}), 1, 8) AS BIGINT) = -9223372036854775808 
    THEN CONVERT(BIGINT, (
        (9223372036854775807) % CONVERT(BIGINT, POWER(CONVERT(DECIMAL(38,0), 10), {{ max_digits }}))
    ))
    ELSE CONVERT(BIGINT, (
        ABS(CAST(SUBSTRING(HASHBYTES('MD5', {{ combined_expression }}), 1, 8) AS BIGINT))
        % CONVERT(BIGINT, POWER(CONVERT(DECIMAL(38,0), 10), {{ max_digits }}))
    ))
END
{% endmacro %}
