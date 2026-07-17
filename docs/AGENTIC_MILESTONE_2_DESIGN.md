# Agentic Semantic Contract — Milestone 2 Design

## Purpose and baseline

Milestone 2 introduces a typed, platform-neutral metric representation and deterministic compilers for the narrow semantic subset already recognized by the POC. The canonical source remains `models/semantic/triathlon_semantic.yml`; the compiled dbt manifest supplies resolved measures and entities. Power BI TMDL and Snowflake Semantic View YAML remain targets.

The accepted Milestone 1 implementation already had useful dictionary normalization, exact target alias resolution, Power BI parsing, expected-DAX comparison, and Snowflake generation. Milestone 2 extends that path rather than adding an independent contract. The legacy normalized dictionaries remain compatibility output, backed by the typed classification during normalization.

## Existing model audit

| Concern | Milestone 1 representation | Milestone 2 decision |
| --- | --- | --- |
| Canonical metrics | Manifest/YAML dictionaries | Convert exact canonical names into immutable `SemanticMetricIR` values. |
| Patterns | `basic_count`, `filtered_count`, `ratio` strings | Central typed registry for `COUNT`, `FILTERED_COUNT`, and `RATIO`; retain legacy strings only in serialized compatibility output. |
| Filters | One parsed boolean column | Ordered `FilterPredicate` values with the shared `EQ` operator. |
| DAX | `expected_dax` string branches | Registry-dispatched deterministic compiler with typed table, column, and measure references. |
| Snowflake | Independent string branches in the view builder | Registry-dispatched metric compiler; the existing builder retains tables, dimensions, relationships, and ordering. |
| Support | String flags | `SUPPORTED_PATTERN`, `MANUAL_REVIEW_REQUIRED`, and `UNSUPPORTED` with structured diagnostics. |
| Traceability | Canonical source comments and change IDs | IR and generation results carry canonical metric, source, semantic signature, and trace ID. |

## Typed IR and invariants

`SemanticMetricIR` is immutable and represents:

- canonical name, label, description, public status, source file/selector, and trace ID;
- source semantic model, primary entity, canonical logical table, and physical table;
- typed pattern, aggregation, source field, ordered filters, and ratio references;
- semantic format plus explicit Power BI and Snowflake mappings;
- support classification and structured diagnostics.

The converter resolves only exact canonical names and exact references from the compiled manifest. A simple metric must resolve to one measure in one semantic model. That model must have one primary entity, and the entity expression must match exactly one canonical logical-table primary key. Ratios inherit a source context only when numerator and denominator contexts are identical. No relationship path is inferred.

Public metrics require complete Power BI and Snowflake mappings. Private support metrics retain the existing deterministic reference behavior: canonical label for DAX and canonical name for Snowflake. Duplicate target aliases or reference labels require manual review.

A caller may supply a future change ID as `trace_id`. Read-only baseline conversion otherwise uses `canonical:<file>#metric:<name>`, which is stable across runs.

## Filter grammar and pattern registry

The only accepted filter grammar is a flat `AND` conjunction of equality predicates:

```text
identifier = typed_literal [AND identifier = typed_literal ...]
```

Literals may be booleans, integers, decimals, or quoted strings. Values `0` and `1` on known boolean fields normalize to booleans. Predicates sort by field, operator, value type, and value representation before compilation.

`OR`, parentheses, unknown comparison operators, functions other than boolean literals, and arbitrary SQL/DAX return `MANUAL_REVIEW_REQUIRED`.

| Pattern | Canonical input | DAX | Snowflake | Status |
| --- | --- | --- | --- | --- |
| `COUNT` | simple `sum/count` of `1` or `*` | `COUNTROWS(table)` | `COUNT(*)` | Supported when the source resolves uniquely. |
| `FILTERED_COUNT` | simple `sum_boolean` with structured `EQ` filters | `CALCULATE( COUNTROWS(table), filters... )` | `COUNT_IF(predicate AND ...)` | Supported for the shared filter grammar. |
| `RATIO` | exact numerator and denominator metric references | `DIVIDE( [Numerator], [Denominator] )` | `numerator / NULLIF(denominator, 0)` | Supported when references and source context are unique. |
| Other | cumulative, conversion, median, nested, or arbitrary logic | None | None | `UNSUPPORTED` or `MANUAL_REVIEW_REQUIRED`; never approximated. |

Each immutable registry entry declares required fields, allowed operators, validator, DAX compiler, Snowflake compiler, and support status.

## Generation and validation flow

The public flow is:

```text
canonical YAML + dbt manifest
    -> canonical_metric_to_ir
    -> classify_pattern
    -> generate_dax_definition
    -> generate_snowflake_definition
    -> validate_cross_target
```

Generation returns an immutable envelope containing the definition, target, support result, diagnostics, trace ID, canonical identity, and semantic signature. The signature covers the canonical metric/source, aggregation, source identity, filters, ratio references, public status, and trace ID.

Cross-target validation compares these signatures; it does not reverse-parse generated formulas and therefore makes no claim about arbitrary formulas. Snowflake metrics enter the existing full-view builder only after this validation succeeds. Trace metadata stays in the in-memory envelope and is not injected into deployable Snowflake YAML.

Identifiers and string literals are escaped by deterministic target-specific functions. Existing safe identifiers preserve current formatting, so current generated outputs remain byte-identical.

## Public Python interfaces

The following are exported from `semantic_poc.src`:

- `canonical_metric_to_ir(...)`
- `classify_pattern(...)`
- `generate_dax_definition(...)`
- `generate_snowflake_definition(...)`
- `validate_cross_target(...)`

Supporting immutable types and `PATTERN_REGISTRY` are also exported for deterministic offline orchestration and testing. There is no canonical apply, TMDL edit, approval, deployment, external connection, or natural-language interface in this milestone.

## Current generated examples

`valid_sbr_finishers`:

```text
CALCULATE( COUNTROWS(fct_result), fct_result[is_valid_sbr_finisher] = TRUE() )
COUNT_IF(is_valid_sbr_finisher)
```

`event_context_rate`:

```text
DIVIDE( [Event Context Rows], [Valid SBR Finishers] )
results.event_context_rows / NULLIF(results.valid_sbr_finishers, 0)
```

The DNS/DNF/DSQ request remains a no-op: `is_valid_sbr_finisher` is derived only for `finish_status = 'FIN'`, and the current target definitions remain a `MATCH`.
