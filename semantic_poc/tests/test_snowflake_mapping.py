from __future__ import annotations

import copy

from semantic_poc.src.models import (
    STATUS_UNSUPPORTED_IN_SNOWFLAKE,
    build_snowflake_semantic_view,
    compare_semantics,
    load_normalized_dbt_semantics,
)


ENVIRONMENT = {
    "database": "TRIATHLON",
    "schema": "MART",
    "semantic_view_schema": "SEMANTIC",
    "semantic_view_name": "TRIATHLON_ANALYTICS",
}


def test_snowflake_yaml_generation_for_filtered_counts_and_ratios() -> None:
    dbt_semantics = load_normalized_dbt_semantics()
    view = build_snowflake_semantic_view(dbt_semantics, ENVIRONMENT)
    results = next(table for table in view["tables"] if table["name"] == "results")
    result_metrics = {metric["name"]: metric for metric in results["metrics"]}
    derived_metrics = {metric["name"]: metric for metric in view["metrics"]}

    assert results["base_table"]["table"] == "FCT_RESULT"
    assert result_metrics["valid_sbr_finishers"]["expr"] == "COUNT_IF(is_valid_sbr_finisher)"
    assert result_metrics["record_integrity_rows"]["access_modifier"] == "private_access"
    assert (
        derived_metrics["event_context_rate"]["expr"]
        == "results.event_context_rows / NULLIF(results.valid_sbr_finishers, 0)"
    )


def test_unsupported_metric_is_marked_for_manual_review() -> None:
    dbt_semantics = load_normalized_dbt_semantics()
    mutated = copy.deepcopy(dbt_semantics)
    unsupported = copy.deepcopy(mutated["metrics"]["event_context_rate"])
    unsupported["name"] = "unsupported_metric"
    unsupported["translation_pattern"] = "cumulative"
    unsupported["snowflake_supported"] = False
    unsupported["snowflake"] = {"logical_table": "results", "metric_name": "unsupported_metric"}
    mutated["metrics"]["unsupported_metric"] = unsupported
    mutated["public_metrics"].append("unsupported_metric")

    view = build_snowflake_semantic_view(mutated, ENVIRONMENT)
    comparison = compare_semantics(mutated, {"tables": {}, "relationships": []}, view)
    row = next(item for item in comparison["rows"] if item["metric"] == "unsupported_metric")

    assert {"metric": "unsupported_metric", "reason": "cumulative"} in view["unsupported_metrics"]
    assert row["status"] == STATUS_UNSUPPORTED_IN_SNOWFLAKE
