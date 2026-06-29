from __future__ import annotations

import copy

import pytest

from semantic_poc.run_poc import (
    PocPaths,
    PocValidationError,
    REPO_ROOT,
    strict_failures,
    run_poc,
    validate_public_metric_set,
    validate_static_inputs,
)
from semantic_poc.src.models import (
    DBT_SEMANTIC_MANIFEST,
    DBT_SEMANTIC_YAML,
    PBI_DEFINITION_DIR,
    REQUIRED_PUBLIC_METRICS,
    SNOWFLAKE_ENVIRONMENT,
    load_yaml,
)


def test_missing_input_validation_is_actionable(tmp_path) -> None:
    paths = PocPaths(
        repo_root=tmp_path,
        dbt_project_dir=tmp_path,
        dbt_semantic_yaml=tmp_path / "models" / "semantic" / "triathlon_semantic.yml",
        semantic_manifest=tmp_path / "target" / "semantic_manifest.json",
        powerbi_definition_dir=tmp_path / "pbi" / "definition",
        snowflake_environment=tmp_path / "semantic_poc" / "config" / "snowflake_environment.yml",
        output_dir=tmp_path / "output",
    )

    with pytest.raises(PocValidationError) as exc_info:
        validate_static_inputs(paths)

    message = str(exc_info.value)
    assert "Canonical dbt semantic YAML is missing" in message
    assert "Checked path: models/semantic/triathlon_semantic.yml" in message
    assert "Fix:" in message


def test_public_metric_validation_names_missing_metric_and_fix() -> None:
    dbt_yaml = copy.deepcopy(load_yaml(DBT_SEMANTIC_YAML))
    for metric in dbt_yaml["metrics"]:
        if metric["name"] == "event_context_rate":
            metric["config"]["meta"]["semantic_contract"]["public"] = False
            break
    paths = PocPaths(
        repo_root=REPO_ROOT,
        dbt_project_dir=REPO_ROOT,
        dbt_semantic_yaml=DBT_SEMANTIC_YAML,
        semantic_manifest=DBT_SEMANTIC_MANIFEST,
        powerbi_definition_dir=PBI_DEFINITION_DIR,
        snowflake_environment=SNOWFLAKE_ENVIRONMENT,
        output_dir=REPO_ROOT / "semantic_poc" / "output",
    )

    with pytest.raises(PocValidationError) as exc_info:
        validate_public_metric_set(dbt_yaml, paths)

    message = str(exc_info.value)
    assert "event_context_rate" in message
    assert "Checked path: models/semantic/triathlon_semantic.yml" in message
    assert "Fix:" in message


def test_poc_outputs_are_deterministic(tmp_path) -> None:
    paths = PocPaths(
        repo_root=REPO_ROOT,
        dbt_project_dir=REPO_ROOT,
        dbt_semantic_yaml=DBT_SEMANTIC_YAML,
        semantic_manifest=DBT_SEMANTIC_MANIFEST,
        powerbi_definition_dir=PBI_DEFINITION_DIR,
        snowflake_environment=SNOWFLAKE_ENVIRONMENT,
        output_dir=tmp_path / "output",
    )

    run_poc(paths, skip_dbt_parse=True)
    first = {path.name: path.read_bytes() for path in paths.output_files}
    run_poc(paths, skip_dbt_parse=True)
    second = {path.name: path.read_bytes() for path in paths.output_files}

    assert first == second
    assert b"Generated file. Do not edit manually." in first["semantic_compatibility.md"]
    assert b'"_generated"' in first["dbt_semantics.json"]


def test_strict_mode_policy_and_metadata_flag(tmp_path) -> None:
    paths = PocPaths(
        repo_root=REPO_ROOT,
        dbt_project_dir=REPO_ROOT,
        dbt_semantic_yaml=DBT_SEMANTIC_YAML,
        semantic_manifest=DBT_SEMANTIC_MANIFEST,
        powerbi_definition_dir=PBI_DEFINITION_DIR,
        snowflake_environment=SNOWFLAKE_ENVIRONMENT,
        output_dir=tmp_path / "output",
    )
    result = run_poc(paths, skip_dbt_parse=True)

    assert strict_failures(result, strict=False, fail_on_metadata_drift=False) == []
    assert strict_failures(result, strict=False, fail_on_metadata_drift=True) == ["Power BI metadata drift exists"]
    failures = strict_failures(result, strict=True, fail_on_metadata_drift=False)
    assert "structural relationship drift exists" in failures
    assert "Power BI metadata drift exists" not in failures
    assert result.summary["Public metrics"] == len(REQUIRED_PUBLIC_METRICS)
