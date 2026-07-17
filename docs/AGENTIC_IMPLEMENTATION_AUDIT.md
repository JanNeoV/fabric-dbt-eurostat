# Agentic Semantic Workflow Implementation Audit

Audit date: 2026-07-17

Audited commit: `79c6d9e63900acf06c2b2b591c67e316084b24ef`

Original branch: `feat/create-new-project`

Implementation branch: `feat/agentic-semantic-contract-m1`

## Repository State

The original working tree contained two untracked files: `AGENTS.md` and an empty root `SKILL.md`. Both were copied to ignored `.tmp/agentic-m1-prechange/` before implementation. A local backup ref, `backup/feat-create-new-project-pre-agentic-m1-20260717-79c6d9e`, points to the audited commit. The repository had no `.agents/skills` content and no GitHub Actions workflows.

The canonical semantic source is `models/semantic/triathlon_semantic.yml`. The checked-in `semantic/triathlon_metric_contract.yml` is a deprecated legacy contract and must not be modified. Generated POC outputs are intentionally committed under `semantic_poc/output/`; live Snowflake verification reports and copied Power BI definitions are ignored.

## Reusable Components

- `semantic_poc/src/models.py` already loads dbt YAML/manifest data, normalizes a supported metric subset, parses Power BI TMDL, generates deterministic expected DAX and Snowflake YAML, and compares target compatibility.
- Public metric `config.meta` blocks already hold Power BI and Snowflake mappings.
- The Power BI patcher already copies the definition directory, limits operations to metadata, verifies protected topology/properties, and has no in-place mode.
- Snowflake verification and deployment are already separate; deployment requires `--apply` and secrets are redacted.
- `run_poc.py` centralizes path validation, generation, summaries, and strict policy. `run_quality_checks.py` runs dbt parse, offline tests, generation, and determinism checks.
- Existing tests cover normalization, target mapping, metadata-only Power BI patch safety, runner behavior, determinism, and opt-in Snowflake verification/deployment behavior.

## Current Internal Representations

| Concern | Existing representation |
| --- | --- |
| Metrics | Dictionaries normalized from `target/semantic_manifest.json` plus canonical YAML metadata |
| Measures | Manifest measure dictionaries keyed by name, with aggregation, expression, and source model |
| Filters | A narrow parser that recognizes one boolean equality and stores `filter_column` |
| Dimensions | Manifest dimension dictionaries plus Snowflake dimension hints/constants |
| Relationships | Canonical metadata dictionaries and parsed TMDL relationship dictionaries, compared by four-part signatures |
| Power BI mappings | `config.meta.power_bi` table, measure, format, and display-folder values |
| Snowflake mappings | `config.meta.snowflake` logical table, metric name, and synonyms |
| Compatibility | String constants such as `MATCH`, `METADATA_DRIFT`, `DEFINITION_DRIFT`, missing-target statuses, and manual/unsupported statuses |

These abstractions are suitable for read-only Milestone 1 inspection. They should be refactored into typed compiler models in Milestone 2 rather than duplicated now.

## Missing Components

- No typed change request, JSON Schema, local store, approval lifecycle, or traceable change ID.
- No unified `semantic-agent` CLI or exact target-alias resolver.
- No proposal engine, canonical diff engine, deterministic definition-operation patch format, or local approval/apply orchestration.
- No optional Codex interface or structured agent-output validation.
- No read-only reconciliation command.
- No CI workflow; all current checks are local and credential-free.

## Architectural Risks

- `semantic_poc/src/models.py` combines parsing, normalization, generation, comparison, and rendering. Large new features added there would increase coupling.
- Normalized semantics depend on an ignored dbt manifest. Inspection must remain useful without it while refusing to claim compatibility.
- The filter model recognizes only a single boolean equality; expanding it without an explicit typed IR could silently mis-translate logic.
- Current compatibility uses combined row statuses, so unsupported target semantics must be normalized to `MANUAL_REVIEW_REQUIRED` for agent decisions.
- Checked-in generated outputs can be rewritten by quality commands; determinism and Git diffs must be checked after validation.
- The canonical `is_valid_sbr_finisher` path already requires `finish_status = 'FIN'`. Treating DNS/DNF/DSQ exclusion as a mutation would create redundant semantics.
- Strict POC validation currently fails because `fct_result.distance_id -> dim_distance.distance_id` is missing in Power BI. This is an existing source-model drift, not a Milestone 1 regression.

## Baseline Validation

- `python -m pytest semantic_poc/tests -q -p no:cacheprovider`: `47 passed, 1 skipped`.
- `python semantic_poc/run_poc.py --skip-dbt-parse --strict` using a temporary output directory: exit `1` with `0` definition drift, `1` structural drift, and `1` manual-review item.
- The strict failure is retained as an acceptance limitation. Milestone 1 must not add another strict finding.

## Milestone 1 Changes and Test Gaps

Milestone 1 adds permanent repository instructions, a repository skill, a stdlib typed change contract/store, an explicit lifecycle transition validator, and read-only inspection shared by the CLI and skill script. User-generated change JSON is ignored while `.gitkeep` remains trackable.

New tests must cover schema round-trips and rejection, path-safe atomic persistence, lifecycle transitions, exact canonical/target resolution, ambiguous and invalid names, missing-manifest fallback, CLI exit codes, repository rules, skill structure, and canonical/Power BI hash preservation.

## Recommended Implementation Order

1. Complete and validate Milestone 1 read-only inspection and typed request infrastructure.
2. Introduce a typed semantic IR and deterministic count/filtered-count/ratio compilers without changing application behavior.
3. Add proposal/show workflows that generate diffs but cannot apply them.
4. Add approval-gated local canonical application and copied Power BI definition operations.
5. Add optional structured Codex interpretation only after deterministic/offline workflows pass acceptance.

Do not begin connected deployment work until Milestones 1–5 pass their acceptance gates.
