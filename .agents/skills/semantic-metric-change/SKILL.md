---
name: semantic-metric-change
description: Inspect and control business-metric changes across the canonical dbt semantic YAML, mapped Power BI measures, and generated Snowflake Semantic Views. Use when Codex is asked to create, update, rename, deprecate, inspect, or reconcile a semantic metric or a mapped Power BI/Snowflake target definition in this repository.
---

# Semantic Metric Change

Keep `models/semantic/triathlon_semantic.yml` canonical. Treat target names as aliases for canonical dbt metrics and never deploy from this workflow.

## Workflow

1. Read `AGENTS.md` and [references/safety-boundaries.md](references/safety-boundaries.md).
2. Classify the intent as `CREATE_METRIC`, `UPDATE_METRIC`, `RENAME_METRIC`, `DEPRECATE_METRIC`, or `RECONCILE_TARGET_DRIFT`.
3. For an existing metric or target alias, inspect it before interpreting the requested change:

   ```bash
   python .agents/skills/semantic-metric-change/scripts/inspect_metric.py valid_sbr_finishers
   ```

4. Resolve only an exact canonical name or an exact case-insensitive mapped Power BI/Snowflake name. Never fuzzy-match. Return `MANUAL_REVIEW_REQUIRED` for ambiguity.
5. Read [references/architecture.md](references/architecture.md) and [references/supported-patterns.md](references/supported-patterns.md) to classify the semantic pattern.
6. Produce a structured `MetricChangeRequest` in proposal mode with a traceable change ID. Record assumptions instead of silently inventing semantics.
7. Detect no-op requests. If current canonical semantics already guarantee the request, explain the evidence and propose no diff.
8. Generate canonical and target proposals only through repository tooling. Final DAX and Snowflake expressions must be deterministic.
9. Run required validation and show canonical, Power BI copy, and Snowflake diffs.
10. Request explicit approval before local application. Never edit the source Power BI definition in place.
11. Apply locally only through supported repository commands after approval. Never deploy or push automatically.

Milestone 1 implements inspection and the typed change model only. Until later milestones add proposal and application commands, stop after inspection/structured planning and report unavailable automation honestly.

## References

- Read [references/architecture.md](references/architecture.md) for source and mapping flow.
- Read [references/supported-patterns.md](references/supported-patterns.md) before classifying target support.
- Read [references/safety-boundaries.md](references/safety-boundaries.md) before any proposed write.
- Read [references/examples.md](references/examples.md) for `valid_sbr_finishers` and `event_context_rate` examples.
