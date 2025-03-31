{% macro generate_tsql_surrogate_key_integer(field_list, max_digits=9) %}
{# 
  Creates a deterministic integer (up to max_digits) by:
   1) Coalescing fields to '' and joining with '|'.
   2) Hashing via HASHBYTES('MD5', ...).
   3) Taking the first 8 bytes => BIGINT => ABS => mod 10^max_digits.
#}

{# 1. Build a Jinja expression that merges fields into one string #}
{% set default_null_value = '' %}
{% set delimiter = '|' %}

{# For each field, we produce e.g. COALESCE(field, '') #}
{% set expression_parts = [] %}
{% for field in field_list %}
    {% do expression_parts.append("COALESCE(" ~ field ~ ", '" ~ default_null_value ~ "')") %}
{% endfor %}

{# Join them with " + '|' + " so it becomes:
   COALESCE(field1, '') + '|' + COALESCE(field2, '') + '|' ...
#}
{% set combined_expression = expression_parts | join(" + '" ~ delimiter ~ "' + ") %}

{# 2. Return the T-SQL snippet that does the hashing #}
ABS(
  CAST(
    SUBSTRING(
      HASHBYTES('MD5', {{ combined_expression }}),
      1,
      8
    ) AS BIGINT
  )
) % CAST(POWER(10, {{ max_digits }}) as BIGINT)
{% endmacro %}
