{% macro dbt_utils__get_relations_by_pattern(
    database=None,
    schema_pattern=None,
    identifier_pattern=None,
    include_external=False
) %}

select
    table_catalog as database_name,
    table_schema as schema_name,
    table_name as identifier
from INFORMATION_SCHEMA.TABLES
where 1=1
      {% if database %} and table_catalog = '{{ database }}' {% endif %}
      {% if schema_pattern %} and upper(table_schema) like upper('{{ schema_pattern }}') {% endif %}
      {% if identifier_pattern %} and upper(table_name) like upper('{{ identifier_pattern }}') {% endif %}
order by table_catalog, table_schema, table_name
{% endmacro %}
