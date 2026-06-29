from __future__ import annotations

import copy

import pytest

from semantic_poc.src.models import (
    REQUIRED_PUBLIC_METRICS,
    DBT_SEMANTIC_MANIFEST,
    DBT_SEMANTIC_YAML,
    load_json,
    load_normalized_dbt_semantics,
    load_yaml,
    normalize_dbt_semantics,
    validate_dbt_semantics,
)


def test_public_metrics_come_from_dbt_meta() -> None:
    data = load_normalized_dbt_semantics()

    assert data["canonical_source"] == "models/semantic/triathlon_semantic.yml"
    assert data["public_metrics"] == REQUIRED_PUBLIC_METRICS
    assert "record_integrity_rows" in data["metrics"]
    assert data["metrics"]["record_integrity_rows"]["public"] is False


def test_contract_validation_and_rate_formats() -> None:
    data = load_normalized_dbt_semantics()

    assert validate_dbt_semantics(data) == []
    for name in REQUIRED_PUBLIC_METRICS:
        metric = data["metrics"][name]
        assert metric["power_bi"]
        assert metric["snowflake"]
        if metric["type"] == "ratio":
            assert metric["numerator"]
            assert metric["denominator"] == "valid_sbr_finishers"
            assert metric["format"] == "percentage_1_decimal"


def test_missing_required_metric_after_parse_fails_clearly() -> None:
    manifest = copy.deepcopy(load_json(DBT_SEMANTIC_MANIFEST))
    dbt_yaml = load_yaml(DBT_SEMANTIC_YAML)
    manifest["metrics"] = [metric for metric in manifest["metrics"] if metric["name"] != "event_context_rate"]

    with pytest.raises(ValueError, match="Missing expected metrics after dbt parse"):
        normalize_dbt_semantics(manifest, dbt_yaml)


def test_eighth_public_metric_can_be_added_from_dbt_yaml_meta_only() -> None:
    manifest = copy.deepcopy(load_json(DBT_SEMANTIC_MANIFEST))
    dbt_yaml = copy.deepcopy(load_yaml(DBT_SEMANTIC_YAML))

    manifest["metrics"].append(
        {
            "name": "example_supported_rows",
            "label": "Example Supported Rows",
            "description": "Example public metric added through dbt YAML metadata.",
            "type": "simple",
            "type_params": {"measure": {"name": "event_context_rows"}},
        }
    )
    dbt_yaml["metrics"].append(
        {
            "name": "example_supported_rows",
            "label": "Example Supported Rows",
            "description": "Example public metric added through dbt YAML metadata.",
            "type": "simple",
            "type_params": {"measure": "event_context_rows"},
            "config": {
                "meta": {
                    "semantic_contract": {"version": 1, "public": True, "format": "whole_number"},
                    "power_bi": {
                        "table": "tri_measures",
                        "measure": "Example Supported Rows",
                        "format_string": "0",
                    },
                    "snowflake": {
                        "logical_table": "results",
                        "metric_name": "example_supported_rows",
                    },
                }
            },
        }
    )

    data = normalize_dbt_semantics(manifest, dbt_yaml)

    assert "example_supported_rows" in data["public_metrics"]
    assert data["metrics"]["example_supported_rows"]["translation_pattern"] == "filtered_count"
