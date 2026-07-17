from __future__ import annotations

import codecs
import json
import shutil
from pathlib import Path

import pytest

from semantic_poc.src.apply_powerbi_patch import (
    apply_powerbi_patch,
    definition_files,
    parse_args,
    partition_blocks,
)
from semantic_poc.src.models import parse_tmdl_definition


BASE_TABLE = """table tri_measures
\tlineageTag: table-tag

\tmeasure 'Event Context Rate' = DIVIDE( [Event Context Rows], [Valid SBR Finishers] )
\t\tlineageTag: measure-tag

\t\tannotation PBI_FormatHint = {"isGeneralNumber":true}

\tcolumn dummy
\t\tdataType: string
\t\tlineageTag: column-tag
\t\tsourceColumn: dummy

\tpartition tri_measures = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t    Source = Table.FromRows({})
\t\t\t\tin
\t\t\t\t    Source
"""

RELATIONSHIPS = """relationship rel_event
\tfromColumn: fct_result.event_id
\ttoColumn: dim_event.event_id
"""


def write_definition(tmp_path: Path, table_text: str = BASE_TABLE) -> Path:
    definition = tmp_path / "definition"
    tables = definition / "tables"
    tables.mkdir(parents=True)
    (tables / "tri_measures.tmdl").write_text(table_text, encoding="utf-8", newline="\n")
    (definition / "relationships.tmdl").write_text(RELATIONSHIPS, encoding="utf-8", newline="\n")
    return definition


def write_patch(tmp_path: Path, operations: list[dict], skipped: list[dict] | None = None) -> Path:
    patch = tmp_path / "proposed_powerbi_patch.json"
    patch.write_text(
        json.dumps({"read_only": True, "operations": operations, "skipped": skipped or []}, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return patch


def apply_single(tmp_path: Path, definition: Path, operations: list[dict], skipped: list[dict] | None = None):
    patch = write_patch(tmp_path, operations, skipped)
    return apply_powerbi_patch(
        definition_dir=definition,
        patch_path=patch,
        output_dir=tmp_path / "patched",
    )


def measure_operation(operation: str, proposed, current=None, measure: str = "Event Context Rate") -> dict:
    return {
        "operation": operation,
        "table": "tri_measures",
        "measure": measure,
        "current": current,
        "proposed": proposed,
        "source": "event_context_rate",
    }


def test_format_string_application(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_format", "0.0%")])

    assert result.success
    assert "\t\tformatString: 0.0%" in (tmp_path / "patched" / "tables" / "tri_measures.tmdl").read_text()


def test_display_folder_application(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_display_folder", "03 Rates")])

    assert result.success
    assert "\t\tdisplayFolder: 03 Rates" in (tmp_path / "patched" / "tables" / "tri_measures.tmdl").read_text()


def test_description_application(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)

    result = apply_single(
        tmp_path,
        definition,
        [measure_operation("set_measure_description", "Share of valid SBR finishers affected by event context.", "")],
    )

    assert result.success
    text = (tmp_path / "patched" / "tables" / "tri_measures.tmdl").read_text()
    assert "\t/// Share of valid SBR finishers affected by event context." in text


def test_table_column_descriptions_and_column_hidden_application(tmp_path: Path) -> None:
    definition = write_definition(tmp_path, BASE_TABLE.replace("\t\tdataType: string\n", "\t\tdataType: string\n").replace("\t\tisHidden\n", ""))
    operations = [
        {
            "operation": "set_table_description",
            "table": "tri_measures",
            "current": "",
            "proposed": "Canonical measure table.",
        },
        {
            "operation": "set_column_description",
            "table": "tri_measures",
            "column": "dummy",
            "current": "",
            "proposed": "Technical placeholder column.",
        },
        {
            "operation": "set_column_hidden",
            "table": "tri_measures",
            "column": "dummy",
            "current": False,
            "proposed": True,
        },
    ]

    result = apply_single(tmp_path, definition, operations)

    assert result.success
    text = (tmp_path / "patched" / "tables" / "tri_measures.tmdl").read_text()
    assert text.startswith("/// Canonical measure table.\ntable tri_measures")
    assert "\t/// Technical placeholder column.\n\tcolumn dummy" in text
    assert "\t\tdataType: string\n\t\tisHidden\n" in text


def test_complete_definition_copy_and_source_tree_preservation(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)
    cultures = definition / "cultures"
    cultures.mkdir()
    (cultures / "en-US.tmdl").write_text("cultureInfo en-US\n", encoding="utf-8")
    (definition / "model.tmdl").write_text("model Model\n", encoding="utf-8")
    before = definition_files(definition)

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_format", "0.0%")])

    assert result.success
    assert definition_files(definition) == before
    assert (tmp_path / "patched" / "cultures" / "en-US.tmdl").read_bytes() == before["cultures/en-US.tmdl"]
    assert set(definition_files(tmp_path / "patched")) == set(before)


def test_unsupported_operation_is_rejected_transactionally(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)
    operation = {
        "operation": "set_measure_dax",
        "table": "tri_measures",
        "measure": "Event Context Rate",
        "current": "old",
        "proposed": "new",
    }

    result = apply_single(tmp_path, definition, [operation])

    assert not result.success
    assert not (tmp_path / "patched").exists()
    assert "outside the safe metadata patch scope" in result.report_path.read_text()


def test_duplicate_patch_operation_is_rejected(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)
    operation = measure_operation("set_measure_format", "0.0%")

    result = apply_single(tmp_path, definition, [operation, operation])

    assert not result.success
    assert "duplicate patch target" in result.report_path.read_text()


def test_unsafe_property_insertion_is_skipped(tmp_path: Path) -> None:
    unsafe_table = BASE_TABLE.replace(
        "\t\tlineageTag: measure-tag\n\n\t\tannotation PBI_FormatHint = {\"isGeneralNumber\":true}",
        "",
    )
    definition = write_definition(tmp_path, unsafe_table)

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_format", "0.0%")])

    assert result.success
    assert not result.applied
    assert any(item["reason"] == "target block could not be modified safely" for item in result.skipped)
    assert "formatString: 0.0%" not in (tmp_path / "patched" / "tables" / "tri_measures.tmdl").read_text()


def test_unknown_measure_rejection(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)

    result = apply_single(
        tmp_path,
        definition,
        [measure_operation("set_measure_format", "0.0%", measure="Missing Rate")],
    )

    assert not result.success
    assert not (tmp_path / "patched").exists()
    assert "does not exist exactly once" in (tmp_path / "powerbi_patch_result.md").read_text()


def test_duplicate_target_rejection(tmp_path: Path) -> None:
    duplicated = BASE_TABLE.replace(
        "\tcolumn dummy",
        "\tmeasure 'Event Context Rate' = 1\n\t\tlineageTag: duplicate-tag\n\n\tcolumn dummy",
    )
    definition = write_definition(tmp_path, duplicated)

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_format", "0.0%")])

    assert not result.success
    assert "ambiguous" in (tmp_path / "powerbi_patch_result.md").read_text()


def test_expected_old_value_mismatch(tmp_path: Path) -> None:
    existing_format = BASE_TABLE.replace(
        "\t\tlineageTag: measure-tag",
        "\t\tformatString: 0.00\n\t\tlineageTag: measure-tag",
    )
    definition = write_definition(tmp_path, existing_format)

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_format", "0.0%")])

    assert not result.success
    assert "expected current value" in (tmp_path / "powerbi_patch_result.md").read_text()


def test_dax_preservation(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)
    source = parse_tmdl_definition(definition, definition)

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_format", "0.0%")])
    patched = parse_tmdl_definition(tmp_path / "patched", tmp_path / "patched")

    assert result.success
    assert (
        source["tables"]["tri_measures"]["measures"]["Event Context Rate"]["expression"]
        == patched["tables"]["tri_measures"]["measures"]["Event Context Rate"]["expression"]
    )


def test_lineage_tag_preservation(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_display_folder", "03 Rates")])
    patched = parse_tmdl_definition(tmp_path / "patched", tmp_path / "patched")

    assert result.success
    assert patched["tables"]["tri_measures"]["lineage_tag"] == "table-tag"
    assert patched["tables"]["tri_measures"]["measures"]["Event Context Rate"]["lineage_tag"] == "measure-tag"


def test_relationship_preservation(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)
    before = (definition / "relationships.tmdl").read_bytes()

    result = apply_single(
        tmp_path,
        definition,
        [measure_operation("set_measure_format", "0.0%")],
        skipped=[
            {
                "item": "fct_result.distance_id -> dim_distance.distance_id",
                "reason": "structural changes are outside the safe patch scope",
            }
        ],
    )

    assert result.success
    assert (tmp_path / "patched" / "relationships.tmdl").read_bytes() == before
    assert "fct_result.distance_id -> dim_distance.distance_id" in (tmp_path / "powerbi_patch_result.md").read_text()


def test_partition_preservation(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)
    before = partition_blocks(definition)

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_format", "0.0%")])

    assert result.success
    assert partition_blocks(tmp_path / "patched") == before


def test_output_folder_only_behaviour(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)
    source_before = (definition / "tables" / "tri_measures.tmdl").read_bytes()

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_format", "0.0%")])

    assert result.success
    assert (definition / "tables" / "tri_measures.tmdl").read_bytes() == source_before
    assert (tmp_path / "patched" / "tables" / "tri_measures.tmdl").is_file()


@pytest.mark.parametrize("output_kind", ["same", "child", "parent", "existing"])
def test_output_path_overlap_and_existing_directory_rejection(tmp_path: Path, output_kind: str) -> None:
    definition = write_definition(tmp_path)
    patch = write_patch(tmp_path, [measure_operation("set_measure_format", "0.0%")])
    if output_kind == "same":
        output = definition
    elif output_kind == "child":
        output = definition / "patched"
    elif output_kind == "parent":
        output = tmp_path
    else:
        output = tmp_path / "existing"
        output.mkdir()

    result = apply_powerbi_patch(definition_dir=definition, patch_path=patch, output_dir=output)

    assert not result.success
    assert definition.is_dir()
    assert any("output" in failure.lower() for failure in result.failures)


def test_cli_has_no_in_place_mode() -> None:
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--definition-dir",
                "definition",
                "--patch",
                "patch.json",
                "--output-dir",
                "patched",
                "--in-place",
            ]
        )


def test_bom_crlf_annotations_and_unrelated_whitespace_are_preserved(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)
    table_path = definition / "tables" / "tri_measures.tmdl"
    crlf_text = BASE_TABLE.replace("\n", "\r\n")
    table_path.write_bytes(codecs.BOM_UTF8 + crlf_text.encode("utf-8"))

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_format", "0.0%")])

    assert result.success
    patched = (tmp_path / "patched" / "tables" / "tri_measures.tmdl").read_bytes()
    assert patched.startswith(codecs.BOM_UTF8)
    decoded = patched[len(codecs.BOM_UTF8) :].decode("utf-8")
    assert "\n" not in decoded.replace("\r\n", "")
    assert '\t\tannotation PBI_FormatHint = {"isGeneralNumber":true}\r\n' in decoded
    assert "\t\t\t\tlet\r\n" in decoded


def test_names_counts_source_mappings_and_artifacts_are_preserved(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)
    source = parse_tmdl_definition(definition, definition)

    result = apply_single(tmp_path, definition, [measure_operation("set_measure_display_folder", "03 Rates")])
    patched = parse_tmdl_definition(tmp_path / "patched", tmp_path / "patched")

    assert result.success
    assert source["tables"].keys() == patched["tables"].keys()
    assert source["tables"]["tri_measures"]["columns"].keys() == patched["tables"]["tri_measures"]["columns"].keys()
    assert source["tables"]["tri_measures"]["measures"].keys() == patched["tables"]["tri_measures"]["measures"].keys()
    assert (
        source["tables"]["tri_measures"]["columns"]["dummy"]["source_column"]
        == patched["tables"]["tri_measures"]["columns"]["dummy"]["source_column"]
    )
    assert result.semantics_path.is_file()
    assert result.compatibility_path.is_file()
    assert "Compatibility before:" in result.report_path.read_text()
    assert "Compatibility after:" in result.report_path.read_text()


def test_idempotency(tmp_path: Path) -> None:
    definition = write_definition(tmp_path)
    patch = write_patch(tmp_path, [measure_operation("set_measure_format", "0.0%")])
    first_output = tmp_path / "patched_first"
    first = apply_powerbi_patch(definition_dir=definition, patch_path=patch, output_dir=first_output)
    second_output = tmp_path / "patched_second"

    second = apply_powerbi_patch(definition_dir=first_output, patch_path=patch, output_dir=second_output)

    assert first.success
    assert second.success
    assert (first_output / "tables" / "tri_measures.tmdl").read_bytes() == (
        second_output / "tables" / "tri_measures.tmdl"
    ).read_bytes()
    assert any(item["reason"] == "already set" for item in second.skipped)


def test_repository_patch_reduces_metadata_drift_and_preserves_structural_drift(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    for filename in [
        "proposed_powerbi_patch.json",
        "dbt_semantics.json",
        "snowflake_semantic_view.yml",
    ]:
        shutil.copy2(repo_root / "semantic_poc" / "output" / filename, artifact_dir / filename)

    result = apply_powerbi_patch(
        definition_dir=repo_root / "pbi" / "triathlon_pbi_model.SemanticModel" / "definition",
        patch_path=artifact_dir / "proposed_powerbi_patch.json",
        output_dir=tmp_path / "patched",
    )

    assert result.success
    assert result.compatibility_before == {"metadata_drift": 5, "structural_drift": 1}
    assert result.compatibility_after == {"metadata_drift": 0, "structural_drift": 1}
    assert len(result.applied) == 10
    assert "METADATA_DRIFT" not in result.compatibility_path.read_text()
