from __future__ import annotations

import json
from pathlib import Path

from semantic_poc.src.apply_powerbi_patch import apply_powerbi_patch, partition_blocks
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
