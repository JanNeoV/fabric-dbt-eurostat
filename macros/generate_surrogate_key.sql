{% macro generate_surrogate_key(field_list) %}
    {%- set parts = [] -%}
    {%- for field in field_list -%}
        {%- do parts.append("coalesce(cast(" ~ field ~ " as varchar(4000)), '_dbt_surrogate_key_null_')") -%}
    {%- endfor -%}
    {%- if parts | length == 1 -%}
        lower(convert(varchar(32), hashbytes('MD5', {{ parts[0] }}), 2))
    {%- else -%}
        lower(convert(varchar(32), hashbytes('MD5', concat({{ parts | join(", '|', ") }})), 2))
    {%- endif -%}
{% endmacro %}
