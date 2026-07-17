# AGENTS.md

## Canonical semantic source

- `models/semantic/triathlon_semantic.yml` is the only canonical semantic contract.
- Treat Power BI TMDL and generated Snowflake YAML as inspected or generated target representations, never independent sources of truth.
- Do not edit the deprecated legacy contract at `semantic/triathlon_metric_contract.yml`.
- A business-semantic change must begin in the canonical contract. Never update only DAX or only Snowflake YAML.
- Resolve requests naming a Power BI measure or Snowflake metric to its mapped canonical dbt metric before proposing a change.

## Safety boundaries

- Proposal mode is the default. Applying local changes requires explicit approval.
- Never modify the source Power BI definition in place. Write approved Power BI changes only to a copied definition folder.
- Never deploy to Power BI Service automatically.
- Never deploy to Snowflake automatically. Verification and deployment must remain separate, and deployment requires an explicit apply operation.
- Never push to GitHub unless the user explicitly requests it after review.
- Never expose, print, or commit API keys, credentials, credential-bearing environment variables, `.env`, profiles, local Power BI state, or live verification reports.
- Do not use `.env` as committed configuration. A redacted `.env.example` is permitted.
- Never silently translate unsupported or ambiguous semantic patterns. Return `MANUAL_REVIEW_REQUIRED` when equivalence cannot be established.
- Do not use an agent or language model to generate final DAX or Snowflake SQL at runtime. Supported target definitions must come from deterministic code.

## Change traceability

- Every generated proposal must have a traceable change ID.
- Every target proposal must identify its canonical source metric and canonical source file.
- Keep proposal, approval, validation, local-application, and deployment states explicit.
- Inspection is read-only and must not create a change request or modify canonical or target files.

## Required validation

After any canonical metric change, run:

1. `dbt --no-version-check parse`
2. `python semantic_poc/run_quality_checks.py`
3. `python semantic_poc/run_poc.py --strict`
4. relevant focused tests

For agent-workflow infrastructure changes, also run the focused agent tests and confirm existing generated outputs and source Power BI files are unchanged.
