from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from semantic_poc.agent.cli import main
from semantic_poc.agent.inspection import MetricAmbiguousError, inspect_metric
from semantic_poc.src.models import (
    DBT_SEMANTIC_MANIFEST,
    DBT_SEMANTIC_YAML,
    PBI_DEFINITION_DIR,
    STATUS_MANUAL_REVIEW_REQUIRED,
    STATUS_MATCH,
    STATUS_METADATA_DRIFT,
    load_yaml,
)


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(item.read_bytes())
    return digest.hexdigest()


def test_inspect_canonical_metric_returns_current_targets() -> None:
    result = inspect_metric("valid_sbr_finishers")

    assert result["resolved_from"] == "CANONICAL"
    assert result["canonical"]["name"] == "valid_sbr_finishers"
    assert result["canonical"]["file"] == "models/semantic/triathlon_semantic.yml"
    assert result["translation_pattern"] == "filtered_count"
    assert result["mappings"]["power_bi"]["exists"] is True
    assert "is_valid_sbr_finisher" in result["mappings"]["power_bi"]["actual_dax"]
    assert result["mappings"]["snowflake"]["generated"] is True
    assert result["compatibility_status"] == STATUS_MATCH


def test_inspect_exact_case_insensitive_target_aliases() -> None:
    power_bi = inspect_metric("valid sbr finishers")
    snowflake = inspect_metric("VALID_SBR_FINISHERS")

    assert power_bi["resolved_from"] == "POWER_BI"
    assert snowflake["resolved_from"] == "SNOWFLAKE"
    assert power_bi["canonical"]["name"] == snowflake["canonical"]["name"] == "valid_sbr_finishers"


def test_inspect_reports_existing_metadata_drift() -> None:
    result = inspect_metric("event context rate")

    assert result["canonical"]["name"] == "event_context_rate"
    assert result["translation_pattern"] == "ratio"
    assert result["compatibility_status"] == STATUS_METADATA_DRIFT


def test_missing_manifest_returns_mapping_and_manual_review(tmp_path: Path) -> None:
    result = inspect_metric("valid_sbr_finishers", manifest_path=tmp_path / "missing.json")

    assert result["canonical"]["name"] == "valid_sbr_finishers"
    assert result["mappings"]["power_bi"]["exists"] is True
    assert result["mappings"]["snowflake"]["generated"] is None
    assert result["compatibility_status"] == STATUS_MANUAL_REVIEW_REQUIRED
    assert "dbt --no-version-check parse" in " ".join(result["diagnostics"])


def test_ambiguous_target_alias_requires_manual_review(tmp_path: Path) -> None:
    data = load_yaml(DBT_SEMANTIC_YAML)
    duplicate = dict(next(metric for metric in data["metrics"] if metric["name"] == "event_context_rate"))
    duplicate["name"] = "duplicate_event_context_rate"
    duplicate["config"] = {
        "meta": {
            "power_bi": {"table": "tri_measures", "measure": "Event Context Rate"},
            "snowflake": {"logical_table": "results", "metric_name": "duplicate_event_context_rate"},
        }
    }
    data["metrics"].append(duplicate)
    semantic_yaml = tmp_path / "semantic.yml"
    semantic_yaml.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    try:
        inspect_metric("EVENT CONTEXT RATE", semantic_yaml_path=semantic_yaml)
    except MetricAmbiguousError as exc:
        assert exc.candidates == ("duplicate_event_context_rate", "event_context_rate")
    else:
        raise AssertionError("Expected ambiguous mapped target name to require manual review.")


def test_cli_json_exit_codes(capsys, tmp_path: Path) -> None:
    assert main(["inspect", "valid_sbr_finishers", "--json"]) == 0
    success = json.loads(capsys.readouterr().out)
    assert success["compatibility_status"] == STATUS_MATCH

    assert main(["inspect", "does_not_exist", "--json"]) == 2
    error = json.loads(capsys.readouterr().out)
    assert error["error"]["code"] == "INVALID_METRIC_NAME"

    assert main(
        ["inspect", "valid_sbr_finishers", "--json", "--manifest", str(tmp_path / "missing.json")]
    ) == 3
    manual = json.loads(capsys.readouterr().out)
    assert manual["compatibility_status"] == STATUS_MANUAL_REVIEW_REQUIRED


def test_cli_json_reports_unreadable_and_malformed_inputs(capsys, tmp_path: Path) -> None:
    missing = tmp_path / "missing-semantic.yml"
    assert main(
        ["inspect", "valid_sbr_finishers", "--json", "--semantic-yaml", str(missing)]
    ) == 3
    unreadable = json.loads(capsys.readouterr().out)
    assert unreadable["error"]["code"] == "INSPECTION_FAILED"
    assert unreadable["error"]["requested_metric"] == "valid_sbr_finishers"

    malformed = tmp_path / "malformed-semantic.yml"
    malformed.write_text("metrics: [\n", encoding="utf-8")
    assert main(
        ["inspect", "valid_sbr_finishers", "--json", "--semantic-yaml", str(malformed)]
    ) == 3
    parsing_error = json.loads(capsys.readouterr().out)
    assert parsing_error["error"]["code"] == "INSPECTION_FAILED"
    assert parsing_error["error"]["requested_metric"] == "valid_sbr_finishers"


def test_inspection_does_not_mutate_canonical_or_powerbi_sources() -> None:
    canonical_before = hashlib.sha256(DBT_SEMANTIC_YAML.read_bytes()).hexdigest()
    powerbi_before = tree_hash(PBI_DEFINITION_DIR)
    manifest_before = hashlib.sha256(DBT_SEMANTIC_MANIFEST.read_bytes()).hexdigest()

    inspect_metric("valid_sbr_finishers")

    assert hashlib.sha256(DBT_SEMANTIC_YAML.read_bytes()).hexdigest() == canonical_before
    assert tree_hash(PBI_DEFINITION_DIR) == powerbi_before
    assert hashlib.sha256(DBT_SEMANTIC_MANIFEST.read_bytes()).hexdigest() == manifest_before
