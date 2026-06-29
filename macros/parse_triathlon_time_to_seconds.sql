{% macro parse_triathlon_time_to_seconds(time_expr) %}
    {%- set clean = "nullif(trim(cast(" ~ time_expr ~ " as varchar(64))), '')" -%}
    {%- set colon_count = "(len(" ~ clean ~ ") - len(replace(" ~ clean ~ ", ':', '')))" -%}
    {%- set hms_hours = "try_cast(parsename(replace(" ~ clean ~ ", ':', '.'), 3) as int)" -%}
    {%- set hms_minutes = "try_cast(parsename(replace(" ~ clean ~ ", ':', '.'), 2) as int)" -%}
    {%- set hms_seconds = "try_cast(parsename(replace(" ~ clean ~ ", ':', '.'), 1) as int)" -%}
    {%- set ms_minutes = "try_cast(parsename(replace(" ~ clean ~ ", ':', '.'), 2) as int)" -%}
    {%- set ms_seconds = "try_cast(parsename(replace(" ~ clean ~ ", ':', '.'), 1) as int)" -%}

    (
        case
            when {{ clean }} is null then null
            when {{ clean }} like '%.%' then null
            when {{ clean }} like '-%' then null
            when {{ colon_count }} = 2 then
                case
                    when {{ hms_hours }} is null
                        or {{ hms_minutes }} is null
                        or {{ hms_seconds }} is null
                        or {{ hms_hours }} < 0
                        or {{ hms_minutes }} < 0
                        or {{ hms_minutes }} > 59
                        or {{ hms_seconds }} < 0
                        or {{ hms_seconds }} > 59
                        or (({{ hms_hours }} * 3600) + ({{ hms_minutes }} * 60) + {{ hms_seconds }}) <= 0
                    then null
                    else ({{ hms_hours }} * 3600) + ({{ hms_minutes }} * 60) + {{ hms_seconds }}
                end
            when {{ colon_count }} = 1 then
                case
                    when {{ ms_minutes }} is null
                        or {{ ms_seconds }} is null
                        or {{ ms_minutes }} < 0
                        or {{ ms_seconds }} < 0
                        or {{ ms_seconds }} > 59
                        or (({{ ms_minutes }} * 60) + {{ ms_seconds }}) <= 0
                    then null
                    else ({{ ms_minutes }} * 60) + {{ ms_seconds }}
                end
            else null
        end
    )
{% endmacro %}
