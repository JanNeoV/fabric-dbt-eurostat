from __future__ import annotations

from semantic_poc.src.models import (
    STATUS_METADATA_DRIFT,
    compare_semantics,
    generate_powerbi_patch,
    load_normalized_dbt_semantics,
    parse_tmdl_definition,
)


def test_powerbi_measure_extraction_preserves_lineage_tag() -> None:
    powerbi = parse_tmdl_definition()
    measure = powerbi["tables"]["tri_measures"]["measures"]["Event Context Rate"]

    assert measure["expression"] == "DIVIDE( [Event Context Rows], [Valid SBR Finishers] )"
    assert measure["lineage_tag"] == "a83b2f7e-ec73-42cf-baeb-322addbc47c6"
    assert measure["format_string"] is None


def test_powerbi_patch_is_metadata_only_for_rate_formats_and_folders() -> None:
    dbt_semantics = load_normalized_dbt_semantics()
    powerbi = parse_tmdl_definition()
    patch = generate_powerbi_patch(dbt_semantics, powerbi)
    operations = patch["operations"]

    assert patch["read_only"] is True
    assert {
        "operation": "set_measure_format",
        "table": "tri_measures",
        "measure": "Event Context Rate",
        "current": None,
        "proposed": "0.0%",
        "source": "event_context_rate",
    } in operations
    assert {
        "operation": "set_measure_display_folder",
        "table": "tri_measures",
        "measure": "Event Context Rate",
        "current": None,
        "proposed": "03 Rates",
        "source": "event_context_rate",
    } in operations


def test_compare_detects_metadata_and_distance_relationship_drift() -> None:
    dbt_semantics = load_normalized_dbt_semantics()
    powerbi = parse_tmdl_definition()
    snowflake = {
        "tables": [{"name": "results", "metrics": [{"name": "valid_sbr_finishers"}, {"name": "event_context_rows"}]}],
        "metrics": [
            {"name": "event_context_rate"},
            {"name": "record_integrity_rate"},
            {"name": "individual_profile_rate"},
            {"name": "model_residual_rate"},
            {"name": "individual_hard_flag_rate"},
        ],
    }

    comparison = compare_semantics(dbt_semantics, powerbi, snowflake)

    event_context = next(row for row in comparison["rows"] if row["metric"] == "event_context_rate")
    assert event_context["status"] == STATUS_METADATA_DRIFT
    assert any(
        "fct_result.distance_id -> dim_distance.distance_id" in finding
        for finding in comparison["findings"]["relationship_drift"]
    )
