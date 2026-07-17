# Semantic POC

This folder contains the semantic contract runner and generators. The repository root `README.md` is the public setup guide.

Run the full POC:

```bash
python semantic_poc/run_poc.py
```

Run with an existing manifest:

```bash
python semantic_poc/run_poc.py --skip-dbt-parse
```

Run quality checks:

```bash
python semantic_poc/run_quality_checks.py
```

Verify generated Snowflake Semantic View YAML against a real Snowflake account:

```bash
python -m pip install -e ".[snowflake]"
python -m semantic_poc.src.verify_snowflake_semantic_view
```

Run the deployment command in verification-only mode:

```bash
python -m semantic_poc.src.deploy_snowflake_semantic_view
```

Create or replace the semantic view only when explicitly requested:

```bash
python -m semantic_poc.src.deploy_snowflake_semantic_view --apply
```

Snowflake credentials must come from environment variables or a Snowflake connector profile. Keep `config/snowflake_environment.yml` limited to non-secret target values.

## Applying a Power BI metadata patch

The command creates a complete copied definition folder and never edits the source in place:

```bash
python -m semantic_poc.src.apply_powerbi_patch \
  --definition-dir pbi/triathlon_pbi_model.SemanticModel/definition \
  --patch semantic_poc/output/proposed_powerbi_patch.json \
  --output-dir semantic_poc/output/patched_powerbi_definition
```

Review the copied TMDL changes:

```bash
git diff --no-index \
  pbi/triathlon_pbi_model.SemanticModel/definition \
  semantic_poc/output/patched_powerbi_definition
```

Copy the PBIP project before using the patched definition. Close Power BI Desktop, replace the copied project's `SemanticModel/definition` folder, and then reopen Desktop to validate the model. Structural relationship drift remains a manual decision and is never applied by this command.

Generated example outputs live in `semantic_poc/output/` and are intentionally committed. The patch command writes `powerbi_patch_result.md`, `patched_powerbi_semantics.json`, and `patched_semantic_compatibility.md`; only the copied definition folder is edited. Snowflake verification writes `snowflake_verification.json` and `snowflake_verification.md` when the optional command runs; deployment requires `--apply`.

Live Snowflake verification reports are local artifacts by default. Commit them only after intentional review and redaction, because real account responses can include environment-specific object names or error details.
