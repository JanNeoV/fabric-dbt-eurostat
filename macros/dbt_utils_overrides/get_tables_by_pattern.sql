{% macro fabric__get_tables_by_pattern_sql(schema_pattern, table_pattern, exclude='', database=target.database) %}

select
    table_schema as table_schema,
    table_name as table_name,
    case
        when t.table_type = 'VIEW' then 'view'
        else 'table'
    end as table_type
from INFORMATION_SCHEMA.TABLES t
where 1=1

  {% if database %} and table_catalog = '{{ database }}' {% endif %}

  {% if schema_pattern %}
    -- Instead of schema ilike '...' do T-SQL-compatible:
    and upper(table_schema) like upper('{{ schema_pattern }}')
  {% endif %}

  {% if table_pattern %}
    and upper(table_name) like upper('{{ table_pattern }}')
  {% endif %}

  {% if exclude %}
    -- to exclude a single pattern, could do:
    and table_name not like '{{ exclude }}'
  {% endif %}

order by table_schema, table_name
;
{% endmacro %}
