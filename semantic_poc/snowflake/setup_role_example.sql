-- Minimal Snowflake role setup example for the semantic POC.
-- Replace all <placeholders> before running. Do not store credentials here.

USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS <semantic_poc_role>;

GRANT USAGE ON WAREHOUSE <warehouse> TO ROLE <semantic_poc_role>;
GRANT USAGE ON DATABASE <database> TO ROLE <semantic_poc_role>;
GRANT USAGE ON SCHEMA <database>.<mart_schema> TO ROLE <semantic_poc_role>;
GRANT USAGE ON SCHEMA <database>.<semantic_schema> TO ROLE <semantic_poc_role>;

GRANT CREATE SEMANTIC VIEW ON SCHEMA <database>.<semantic_schema> TO ROLE <semantic_poc_role>;

GRANT SELECT ON TABLE <database>.<mart_schema>.FCT_RESULT TO ROLE <semantic_poc_role>;
GRANT SELECT ON TABLE <database>.<mart_schema>.DIM_EVENT TO ROLE <semantic_poc_role>;
GRANT SELECT ON TABLE <database>.<mart_schema>.DIM_DIVISION TO ROLE <semantic_poc_role>;
GRANT SELECT ON TABLE <database>.<mart_schema>.DIM_GENDER TO ROLE <semantic_poc_role>;
GRANT SELECT ON TABLE <database>.<mart_schema>.DIM_DISTANCE TO ROLE <semantic_poc_role>;

-- If the base objects are views, grant SELECT ON VIEW for those objects instead.
-- Replacing an existing same-named semantic view requires OWNERSHIP on that
-- semantic view or an intentional ownership-transfer deployment process.
-- Do not grant broad account-level privileges for this POC.
