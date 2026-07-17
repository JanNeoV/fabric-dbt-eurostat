# Safety Boundaries

- Keep `models/semantic/triathlon_semantic.yml` canonical.
- Do not edit `semantic/triathlon_metric_contract.yml`.
- Default to proposal mode.
- Require explicit approval before local application.
- Never mutate the source Power BI definition. Use a fresh copied definition folder.
- Never deploy to Power BI Service or Snowflake automatically.
- Never push automatically.
- Never log or commit credentials, `.env`, profiles, local Power BI state, or live verification reports.
- Use deterministic compilers for final DAX and Snowflake expressions.
- Return `MANUAL_REVIEW_REQUIRED` whenever semantic equivalence is unsupported or ambiguous.
- Attach a change ID and canonical metric name to every proposal and generated target operation.
