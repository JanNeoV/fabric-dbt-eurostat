# Architecture

`models/semantic/triathlon_semantic.yml` is the only semantic source of truth. dbt compiles it to `target/semantic_manifest.json`; the POC normalizes that manifest, reads Power BI TMDL, generates Snowflake Semantic View YAML, and compares the three representations.

Public metric `config.meta` blocks contain mappings:

- `power_bi.table` and `power_bi.measure`
- `snowflake.logical_table` and `snowflake.metric_name`

Interpret a named Power BI measure or Snowflake metric as an alias for its mapped canonical dbt metric. Inspect targets to detect drift, but never reverse arbitrary DAX or Snowflake SQL into canonical semantics.

The intended workflow is:

```text
User request -> structured change request -> canonical proposal
             -> normalized semantic representation
             -> deterministic Power BI/Snowflake proposals
             -> validation -> approval -> local-only application
```

Milestone 1 exposes only read-only inspection and typed local change records. Proposal and application commands are future milestones.
