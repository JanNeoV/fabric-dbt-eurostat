# Agentic Semantic Contract — Milestone 2 Report

Report date: 2026-07-17

Source branch: `feat/agentic-semantic-contract-m1`

Starting commit: `e9ce8ab239616d186667c29efeb89d0e2eceb115`

Implementation branch: `feat/agentic-semantic-contract-m2`

Local backup ref: `backup/feat-agentic-semantic-contract-m1-pre-m2-20260717-e9ce8ab`

## Outcome

Milestone 2 adds one immutable semantic IR, a central pattern registry, deterministic Power BI DAX and Snowflake metric compilers, structured diagnostics, source/trace signatures, and cross-target validation. The existing normalizer and full Snowflake view builder use the typed classification/compiler path while retaining their Milestone 1 serialized output.

The accepted commit and its report produced `65 passed, 1 skipped`; this is the repository-backed baseline, superseding the roadmap text's stale count of 64. Milestone 2 finishes with `77 passed, 1 skipped`.

No canonical metric meaning, Power BI source definition, generated artifact, apply path, or deployment behavior changed.

## IR and pattern matrix

The IR records canonical identity/location, label, description, public status, semantic model, primary entity, canonical logical/physical source, aggregation, source field, ordered typed filters, ratio references, formats, target mappings, trace ID, diagnostics, and support classification.

| Pattern | Supported canonical shape | DAX | Snowflake | Refusal boundary |
| --- | --- | --- | --- | --- |
| `COUNT` | simple `sum/count` over `1` or `*` | `COUNTROWS(table)` | `COUNT(*)` | Non-row-count aggregations are unsupported. |
| `FILTERED_COUNT` | `sum_boolean` using flat `AND` equality predicates | stable `CALCULATE` filters | stable `COUNT_IF` predicate | Unknown operators, `OR`, nesting, or arbitrary expressions require manual review. |
| `RATIO` | exact numerator and denominator references with one source context | `DIVIDE` over measures | division with `NULLIF(..., 0)` | Missing/ambiguous references or relationship inference require manual review. |

Public target mappings are mandatory. Private support metrics retain exact canonical label/name references. Duplicate target aliases or measure labels are refused.

## Generated examples

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

Both target result envelopes carry the same canonical metric/source, aggregation, filters, ratio references, public status, and trace ID. Cross-target validation compares those signatures without reverse-engineering arbitrary formulas.

## Files added or modified

- Added `semantic_poc/src/semantic_ir.py` with typed models, strict filter parsing, the immutable registry, deterministic compilers, and cross-target validation.
- Updated `semantic_poc/src/models.py` to classify normalized metrics through the IR and compile current Snowflake definitions through the shared generators.
- Updated `semantic_poc/src/__init__.py` with the stable public interfaces and supporting types.
- Added `semantic_poc/tests/test_semantic_ir.py` with 12 golden, determinism, escaping, refusal, signature, and no-op tests.
- Added `docs/AGENTIC_MILESTONE_2_DESIGN.md` and this report.

The canonical contract, deprecated contract, source Power BI definition, and committed files under `semantic_poc/output/` have no final diff.

## Validation results

| Command | Exit | Exact result |
| --- | ---: | --- |
| `python -m compileall semantic_poc/src semantic_poc/agent` | 0 | All listed modules compiled successfully. |
| Focused IR/contract/Power BI/Snowflake/inspection pytest command | 0 | `29 passed in 2.58s` |
| Focused Milestone 1 agent pytest command | 0 | `18 passed in 1.98s` |
| `python -m pytest semantic_poc/tests -q -p no:cacheprovider` | 0 | `77 passed, 1 skipped in 6.35s` |
| `dbt --no-version-check parse` | 0 | dbt `1.10.13`, Fabric adapter `1.9.7`; parse completed. |
| `python semantic_poc/run_quality_checks.py` | 0 | `77 passed, 1 skipped`; generation and determinism passed. |
| `python semantic_poc/run_poc.py --strict` | 1 | Expected baseline failure only: `structural relationship drift exists`. Definition drift remained 0. |
| Two `run_poc.py --skip-dbt-parse --output-dir ...` passes | 0 / 0 | Both produced identical summaries and output sets. |
| SHA-256 comparison of both temporary generations | 0 | All five output hashes matched. |
| `git diff --check` | 0 | No whitespace errors. |
| Protected-source `git diff --exit-code` | 0 | Canonical, deprecated, and Power BI source paths unchanged. |
| Generated-output `git diff --exit-code` | 0 | All committed generated outputs unchanged. |
| `git diff --cached` | 0 | No staged changes. |

Final temporary-generation SHA-256 values:

| Output | SHA-256 |
| --- | --- |
| `dbt_semantics.json` | `d85e5638ff2cab4ed57fcbf40dc4a515a062b5503d243b295a2a9ab43fa043f9` |
| `powerbi_semantics.json` | `c9051e72e430da21976c76bb98fb806b1c38723e2562ff2d922d848dd8efe3a5` |
| `proposed_powerbi_patch.json` | `e47d4a5aafc9031a4206821212408a6a12dae3e0de889e24c645db8b384c0ebf` |
| `semantic_compatibility.md` | `0b3ced989915b54656281b1ea598dadb827c2553b4d0b5c6627f28d64fd208c3` |
| `snowflake_semantic_view.yml` | `15f705826f284b974477ffd85d66655885527c72ff52bd4ac3f18ade8126ccdb` |

Git blob comparisons against the starting commit also matched for the canonical contract, deprecated contract, and all five committed generated outputs. The accepted Power BI definition tree at the starting commit is `3e723afa2d84b1c650d48205c611eefd3ba67e13`, with no working-tree diff under that definition.

## Expected and unexpected findings

The sole final strict finding is the accepted baseline relationship drift:

```text
fct_result.distance_id -> dim_distance.distance_id is missing in Power BI.
```

No new definition, structural, or unsupported-translation finding was introduced.

During implementation, the compatibility adapter initially exposed the newly resolved ratio source model in `dbt_semantics.json`, changing five legacy `null` values. The generated-output gate caught this before acceptance. The adapter was corrected, outputs were regenerated, and the final Git blob comparisons match the starting commit.

The DNS/DNF/DSQ request remains a traced no-op. The upstream model requires `finish_status = 'FIN'` for `is_valid_sbr_finisher`; inspection still returns `MATCH`, and neither target definition changed.

## Security and deployment status

- No credentials, `.env`, profile contents, local Power BI state, or live verification reports were added or printed.
- No Power BI or Snowflake connection was attempted.
- No canonical apply, TMDL edit, copied-definition application, approval workflow, or deployment interface was added.
- Nothing was committed, staged, pushed, tagged, deployed, or opened as a pull request.

## Limitations and verdict

The supported language remains intentionally narrow. Arbitrary DAX/SQL, nested filters, non-equality operators, cross-source ratios, uncertain relationships, and non-row-count aggregations are not translated. They return structured `MANUAL_REVIEW_REQUIRED` or `UNSUPPORTED` results.

The existing Power BI distance relationship requires the documented manual topology decision and remains the only accepted strict limitation.

Verdict: `MILESTONE_2_ACCEPTED_WITH_LIMITATIONS`

Recommended next step: begin Milestone 3 proposal/show workflows using `MetricChangeRequest.change_id` as the IR trace ID, while keeping canonical and target application disabled.
