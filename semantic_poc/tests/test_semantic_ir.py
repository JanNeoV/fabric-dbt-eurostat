from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace

from semantic_poc.agent.inspection import inspect_metric
from semantic_poc.src import (
    FilterOperator,
    FilterPredicate,
    MetricPattern,
    SupportClassification,
    canonical_metric_to_ir,
    classify_pattern,
    generate_dax_definition,
    generate_snowflake_definition,
    validate_cross_target,
)
from semantic_poc.src.models import (
    CANONICAL_SOURCE,
    DBT_SEMANTIC_MANIFEST,
    DBT_SEMANTIC_YAML,
    STATUS_MATCH,
    load_json,
    load_yaml,
)
from semantic_poc.src.semantic_ir import build_metric_ir_index


def canonical_inputs():
    return load_json(DBT_SEMANTIC_MANIFEST), load_yaml(DBT_SEMANTIC_YAML)


def ir_index(*, manifest=None, canonical_yaml=None, trace_id=None):
    source_manifest, source_yaml = canonical_inputs()
    return build_metric_ir_index(
        manifest or source_manifest,
        canonical_yaml or source_yaml,
        canonical_source=CANONICAL_SOURCE,
        trace_id=trace_id,
    )


def manifest_measure(manifest, name):
    return next(
        measure
        for model in manifest["semantic_models"]
        for measure in model["measures"]
        if measure["name"] == name
    )


def manifest_metric(manifest, name):
    return next(metric for metric in manifest["metrics"] if metric["name"] == name)


def yaml_metric(canonical_yaml, name):
    return next(metric for metric in canonical_yaml["metrics"] if metric["name"] == name)


def test_public_interface_preserves_explicit_and_stable_default_trace_ids() -> None:
    manifest, canonical_yaml = canonical_inputs()
    explicit = canonical_metric_to_ir(
        "valid_sbr_finishers",
        manifest,
        canonical_yaml,
        canonical_source=CANONICAL_SOURCE,
        trace_id="chg_20260717T123045Z_a1b2c3d4",
    )
    implicit = canonical_metric_to_ir(
        "valid_sbr_finishers",
        manifest,
        canonical_yaml,
        canonical_source=CANONICAL_SOURCE,
    )

    assert explicit.trace_id == "chg_20260717T123045Z_a1b2c3d4"
    assert implicit.trace_id == "canonical:models/semantic/triathlon_semantic.yml#metric:valid_sbr_finishers"
    assert implicit.source.selector == "metrics[valid_sbr_finishers]"
    assert implicit.source_semantic_model == "triathlon_results"
    assert implicit.source_entity == "result"
    assert implicit.source_logical_table == "results"
    assert implicit.source_physical_table == "fct_result"


def test_golden_current_filtered_count_and_ratio_definitions() -> None:
    index = ir_index(trace_id="trace_m2_golden")
    filtered = index["valid_sbr_finishers"]
    ratio = index["event_context_rate"]

    filtered_dax = generate_dax_definition(filtered, index)
    filtered_snowflake = generate_snowflake_definition(filtered, index)
    ratio_dax = generate_dax_definition(ratio, index)
    ratio_snowflake = generate_snowflake_definition(ratio, index)

    assert filtered.pattern is MetricPattern.FILTERED_COUNT
    assert filtered.filters == (FilterPredicate("is_valid_sbr_finisher", FilterOperator.EQ, True),)
    assert filtered_dax.definition == "CALCULATE( COUNTROWS(fct_result), fct_result[is_valid_sbr_finisher] = TRUE() )"
    assert filtered_snowflake.definition["expr"] == "COUNT_IF(is_valid_sbr_finisher)"
    assert ratio.pattern is MetricPattern.RATIO
    assert ratio_dax.definition == "DIVIDE( [Event Context Rows], [Valid SBR Finishers] )"
    assert ratio_snowflake.definition["expr"] == (
        "results.event_context_rows / NULLIF(results.valid_sbr_finishers, 0)"
    )
    assert validate_cross_target(filtered, filtered_dax, filtered_snowflake).valid is True
    assert validate_cross_target(ratio, ratio_dax, ratio_snowflake).valid is True


def test_golden_simple_count() -> None:
    index = ir_index()
    metric = index["result_rows"]

    assert metric.pattern is MetricPattern.COUNT
    assert classify_pattern(metric).support is SupportClassification.SUPPORTED_PATTERN
    assert generate_dax_definition(metric, index).definition == "COUNTROWS(fct_result)"
    assert generate_snowflake_definition(metric, index).definition["expr"] == "COUNT(*)"


def test_filter_order_is_canonical_and_generation_hashes_match() -> None:
    index = ir_index()
    base = index["valid_sbr_finishers"]
    first = replace(
        base,
        filters=(
            FilterPredicate("z_flag", FilterOperator.EQ, True),
            FilterPredicate("alpha_status", FilterOperator.EQ, "FIN"),
        ),
    )
    second = replace(base, filters=tuple(reversed(first.filters)))
    first_index = {**index, first.canonical_name: first}
    second_index = {**index, second.canonical_name: second}

    first_dax = generate_dax_definition(first, first_index)
    second_dax = generate_dax_definition(second, second_index)
    first_snowflake = generate_snowflake_definition(first, first_index)
    second_snowflake = generate_snowflake_definition(second, second_index)
    first_bytes = json.dumps(
        {"dax": first_dax.definition, "snowflake": first_snowflake.definition},
        sort_keys=True,
    ).encode()
    second_bytes = json.dumps(
        {"dax": second_dax.definition, "snowflake": second_snowflake.definition},
        sort_keys=True,
    ).encode()

    assert first.filters == second.filters
    assert first_dax.definition == second_dax.definition
    assert first_snowflake.definition == second_snowflake.definition
    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(second_bytes).hexdigest()
    assert first_dax.definition == (
        'CALCULATE( COUNTROWS(fct_result), fct_result[alpha_status] = "FIN", '
        "fct_result[z_flag] = TRUE() )"
    )


def test_identifier_and_literal_escaping_is_deterministic() -> None:
    index = ir_index()
    base = index["valid_sbr_finishers"]
    escaped = replace(
        base,
        source_physical_table="Fact O'Results",
        filters=(FilterPredicate("weird]field", FilterOperator.EQ, 'A "quote"'),),
    )
    escaped_index = {**index, escaped.canonical_name: escaped}

    dax = generate_dax_definition(escaped, escaped_index)
    snowflake = generate_snowflake_definition(escaped, escaped_index)

    assert dax.definition == (
        "CALCULATE( COUNTROWS('Fact O''Results'), "
        "'Fact O''Results'[weird]]field] = \"A \"\"quote\"\"\" )"
    )
    assert snowflake.definition["expr"] == 'COUNT_IF("weird]field" = \'A "quote"\')'


def test_nested_logic_and_unknown_operator_require_manual_review() -> None:
    manifest, canonical_yaml = canonical_inputs()
    nested = copy.deepcopy(manifest)
    manifest_measure(nested, "valid_sbr_finishers")["expr"] = "(is_valid_sbr_finisher = 1 OR any_review_flag = 0)"
    nested_metric = ir_index(manifest=nested, canonical_yaml=canonical_yaml)["valid_sbr_finishers"]

    unknown = copy.deepcopy(manifest)
    manifest_measure(unknown, "valid_sbr_finishers")["expr"] = "finish_status != 'DNS'"
    unknown_metric = ir_index(manifest=unknown, canonical_yaml=canonical_yaml)["valid_sbr_finishers"]

    assert nested_metric.support is SupportClassification.MANUAL_REVIEW_REQUIRED
    assert {item.code for item in nested_metric.diagnostics} == {"FILTER_NESTED_LOGIC_UNSUPPORTED"}
    assert unknown_metric.support is SupportClassification.MANUAL_REVIEW_REQUIRED
    assert {item.code for item in unknown_metric.diagnostics} == {"FILTER_OPERATOR_UNSUPPORTED"}


def test_missing_mapping_and_relationship_refusal_are_structured() -> None:
    manifest, canonical_yaml = canonical_inputs()
    missing_mapping_yaml = copy.deepcopy(canonical_yaml)
    del yaml_metric(missing_mapping_yaml, "valid_sbr_finishers")["config"]["meta"]["power_bi"]
    missing = ir_index(manifest=manifest, canonical_yaml=missing_mapping_yaml)["valid_sbr_finishers"]

    relationship_yaml = copy.deepcopy(canonical_yaml)
    yaml_metric(relationship_yaml, "event_context_rate")["config"]["meta"]["snowflake"]["logical_table"] = "events"
    relationship = ir_index(manifest=manifest, canonical_yaml=relationship_yaml)["event_context_rate"]

    assert missing.support is SupportClassification.MANUAL_REVIEW_REQUIRED
    assert "POWER_BI_MAPPING_MISSING" in {item.code for item in missing.diagnostics}
    assert generate_dax_definition(missing, {missing.canonical_name: missing}).definition is None
    assert relationship.support is SupportClassification.MANUAL_REVIEW_REQUIRED
    assert "SNOWFLAKE_RELATIONSHIP_UNSUPPORTED" in {item.code for item in relationship.diagnostics}


def test_missing_and_ambiguous_ratio_references_require_manual_review() -> None:
    manifest, canonical_yaml = canonical_inputs()
    missing_manifest = copy.deepcopy(manifest)
    manifest_metric(missing_manifest, "event_context_rate")["type_params"]["numerator"]["name"] = "missing_rows"
    missing = ir_index(manifest=missing_manifest, canonical_yaml=canonical_yaml)["event_context_rate"]

    ambiguous_manifest = copy.deepcopy(manifest)
    duplicate = copy.deepcopy(manifest_metric(ambiguous_manifest, "event_context_rows"))
    ambiguous_manifest["metrics"].append(duplicate)
    ambiguous = ir_index(manifest=ambiguous_manifest, canonical_yaml=canonical_yaml)["event_context_rate"]

    assert missing.support is SupportClassification.MANUAL_REVIEW_REQUIRED
    assert "RATIO_REFERENCE_UNSUPPORTED" in {item.code for item in missing.diagnostics}
    assert ambiguous.support is SupportClassification.MANUAL_REVIEW_REQUIRED
    assert "RATIO_REFERENCE_UNSUPPORTED" in {item.code for item in ambiguous.diagnostics}


def test_duplicate_measure_labels_refuse_ratio_dax_generation() -> None:
    manifest, canonical_yaml = canonical_inputs()
    duplicate_label_manifest = copy.deepcopy(manifest)
    manifest_metric(duplicate_label_manifest, "finishers")["label"] = "Valid SBR Finishers"
    index = ir_index(manifest=duplicate_label_manifest, canonical_yaml=canonical_yaml)
    ratio = index["event_context_rate"]
    result = generate_dax_definition(ratio, index)

    assert result.support is SupportClassification.MANUAL_REVIEW_REQUIRED
    assert result.definition is None
    assert result.diagnostics[0].code == "POWER_BI_REFERENCE_AMBIGUOUS"


def test_unknown_metric_family_is_unsupported() -> None:
    manifest, canonical_yaml = canonical_inputs()
    unsupported_manifest = copy.deepcopy(manifest)
    manifest_metric(unsupported_manifest, "event_context_rate")["type"] = "cumulative"
    unsupported = ir_index(manifest=unsupported_manifest, canonical_yaml=canonical_yaml)["event_context_rate"]

    assert unsupported.pattern is None
    assert classify_pattern(unsupported).support is SupportClassification.UNSUPPORTED


def test_cross_target_validation_rejects_tampered_signature() -> None:
    index = ir_index(trace_id="trace_cross_target")
    metric = index["event_context_rate"]
    dax = generate_dax_definition(metric, index)
    snowflake = generate_snowflake_definition(metric, index)
    tampered = replace(snowflake, signature=replace(snowflake.signature, public=False))

    result = validate_cross_target(metric, dax, tampered)

    assert result.valid is False
    assert result.support is SupportClassification.MANUAL_REVIEW_REQUIRED
    assert "SEMANTIC_SIGNATURE_MISMATCH" in {item.code for item in result.diagnostics}


def test_dns_dnf_dsq_request_remains_no_op_and_match() -> None:
    source = (DBT_SEMANTIC_YAML.parents[1] / "intermediate" / "int_result_times.sql").read_text(encoding="utf-8")
    index = ir_index()
    metric = index["valid_sbr_finishers"]

    assert "finish_status = 'FIN'" in source
    assert metric.filters == (FilterPredicate("is_valid_sbr_finisher", FilterOperator.EQ, True),)
    assert generate_dax_definition(metric, index).definition == (
        "CALCULATE( COUNTROWS(fct_result), fct_result[is_valid_sbr_finisher] = TRUE() )"
    )
    assert generate_snowflake_definition(metric, index).definition["expr"] == "COUNT_IF(is_valid_sbr_finisher)"
    assert inspect_metric("valid_sbr_finishers")["compatibility_status"] == STATUS_MATCH
