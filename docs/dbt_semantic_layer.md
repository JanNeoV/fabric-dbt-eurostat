# dbt Semantic Layer

This project uses the dbt Semantic Layer to express the triathlon metric contract in dbt. It is not the same artifact as Snowflake Semantic Views. The dbt layer lives in dbt YAML and is evaluated through dbt's semantic interfaces, while Snowflake Semantic Views are Snowflake-native objects that can be implemented later from the same business contract.

The dbt metrics should reconcile to the existing Power BI semantic model, especially the `tri_measures` table. The intent is semantic equivalence, not a mechanical copy of the Power BI model structure.

The result-grain semantic model is built on `sem_results_obt`, a semantic-facing one-big-table that joins `fct_result` to event, division, gender, and distance dimensions. It intentionally excludes direct athlete identifiers such as name, bib, and country.

The `metricflow_time_spine` model is dbt Semantic Layer support infrastructure. It supplies the day-grain calendar that dbt requires for semantic metric validation and time-grain expansion.

Review flags are review signals, not accusations. They identify rows that need context, data-quality review, or race-level interpretation before any conclusion is drawn.

`valid_sbr_finishers` is the default denominator for athlete-level review rates. It counts finishers with valid gender and complete swim, bike, and run splits, which keeps review-rate comparisons aligned across Power BI, dbt, and future Snowflake Semantic Views.
