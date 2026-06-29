from __future__ import annotations

import argparse
import codecs
import re
import shutil
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .models import (
    clean_tmdl_identifier,
    clean_tmdl_value,
    load_json,
    normalize_expression,
    normalize_text,
    parse_tmdl_definition,
    relative_posix,
)


ALLOWED_OPERATIONS = {
    "set_measure_description",
    "set_measure_format",
    "set_measure_display_folder",
    "set_table_description",
    "set_column_description",
    "set_column_hidden",
}

MEASURE_PROPERTY_OPERATIONS = {
    "set_measure_format": ("formatString", "formatString"),
    "set_measure_display_folder": ("displayFolder", "displayFolder"),
}

PROTECTED_CHECKS = [
    "DAX expressions unchanged",
    "lineage tags unchanged",
    "relationships unchanged",
    "partitions unchanged",
    "table and column counts unchanged",
    "measure counts unchanged",
]


@dataclass(frozen=True)
class TmdlBlock:
    kind: str
    name: str
    header: int
    start: int
    end: int


@dataclass
class TmdlDocument:
    path: Path
    encoding: str
    newline: str
    lines: list[str]
    had_final_newline: bool
    changed: bool = False

    @classmethod
    def load(cls, path: Path) -> "TmdlDocument":
        data = path.read_bytes()
        encoding = "utf-8-sig" if data.startswith(codecs.BOM_UTF8) else "utf-8"
        text = data.decode(encoding)
        newline = "\r\n" if "\r\n" in text else "\n"
        return cls(
            path=path,
            encoding=encoding,
            newline=newline,
            lines=text.splitlines(),
            had_final_newline=text.endswith(("\n", "\r\n")),
        )

    def render(self) -> str:
        text = self.newline.join(self.lines)
        if self.had_final_newline:
            text += self.newline
        return text

    def write_if_changed(self) -> None:
        if self.changed:
            self.path.write_bytes(self.render().encode(self.encoding))

    def block_text(self, block: TmdlBlock) -> str:
        return self.newline.join(self.lines[block.header : block.end])

    def blocks(self) -> dict[str, dict[str, list[TmdlBlock]]]:
        headers: list[tuple[int, str, str]] = []
        for index, line in enumerate(self.lines):
            parsed = parse_header(line)
            if parsed:
                kind, name = parsed
                headers.append((index, kind, name))

        blocks: dict[str, dict[str, list[TmdlBlock]]] = {
            "table": {},
            "measure": {},
            "column": {},
            "partition": {},
        }
        for position, (header, kind, name) in enumerate(headers):
            next_header = headers[position + 1][0] if position + 1 < len(headers) else len(self.lines)
            start = description_start(self.lines, header)
            end = description_start(self.lines, next_header) if next_header < len(self.lines) else len(self.lines)
            blocks[kind].setdefault(name, []).append(TmdlBlock(kind, name, header, start, end))
        return blocks

    def unique_block(self, kind: str, name: str) -> tuple[TmdlBlock | None, str | None]:
        matches = self.blocks().get(kind, {}).get(name, [])
        if len(matches) == 1:
            return matches[0], None
        if not matches:
            return None, f"{kind} `{name}` does not exist exactly once"
        return None, f"{kind} `{name}` is ambiguous ({len(matches)} matches)"


@dataclass
class DefinitionDocuments:
    definition_dir: Path
    tables: dict[str, list[TmdlDocument]]

    @classmethod
    def load(cls, definition_dir: Path) -> "DefinitionDocuments":
        tables: dict[str, list[TmdlDocument]] = {}
        for path in sorted((definition_dir / "tables").glob("*.tmdl")):
            document = TmdlDocument.load(path)
            table_blocks = document.blocks()["table"]
            table_name = next(iter(table_blocks.keys()), path.stem)
            tables.setdefault(table_name, []).append(document)
        return cls(definition_dir=definition_dir, tables=tables)

    def table_document(self, table_name: str) -> tuple[TmdlDocument | None, str | None]:
        matches = self.tables.get(table_name, [])
        if len(matches) == 1:
            return matches[0], None
        if not matches:
            return None, f"table `{table_name}` does not exist exactly once"
        return None, f"table `{table_name}` is ambiguous ({len(matches)} matches)"

    def write_changed(self) -> None:
        for documents in self.tables.values():
            for document in documents:
                document.write_if_changed()


@dataclass(frozen=True)
class PreparedOperation:
    operation: dict[str, Any]
    label: str


@dataclass
class PatchApplyResult:
    success: bool
    output_dir: Path
    report_path: Path
    applied: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    protected_checks: list[str] = field(default_factory=lambda: PROTECTED_CHECKS.copy())


@dataclass(frozen=True)
class ProtectedSnapshot:
    semantics: dict[str, Any]
    relationships: bytes
    partitions: dict[tuple[str, str], str]


def parse_header(line: str) -> tuple[str, str] | None:
    table_match = re.match(r"^table\s+(.+)$", line)
    if table_match:
        return "table", clean_tmdl_identifier(table_match.group(1))
    measure_match = re.match(r"^\tmeasure\s+(.+?)\s*=", line)
    if measure_match:
        return "measure", clean_tmdl_identifier(measure_match.group(1))
    column_match = re.match(r"^\tcolumn\s+(.+)$", line)
    if column_match:
        return "column", clean_tmdl_identifier(column_match.group(1))
    partition_match = re.match(r"^\tpartition\s+(.+?)\s*=", line)
    if partition_match:
        return "partition", clean_tmdl_identifier(partition_match.group(1))
    return None


def description_start(lines: list[str], header: int) -> int:
    start = header
    while start > 0 and lines[start - 1].strip().startswith("///"):
        start -= 1
    return start


def read_description(document: TmdlDocument, block: TmdlBlock) -> str:
    comments = []
    for line in document.lines[block.start : block.header]:
        stripped = line.strip()
        if stripped.startswith("///"):
            comments.append(stripped[3:].strip())
    return normalize_text(" ".join(comments))


def comment_lines(description: str, indent: str) -> list[str]:
    wrapped = textwrap.wrap(description, width=max(40, 96 - len(indent) - 4)) or [description]
    return [f"{indent}/// {line}" for line in wrapped]


def set_description(document: TmdlDocument, block: TmdlBlock, description: str) -> bool:
    indent = re.match(r"^(\s*)", document.lines[block.header]).group(1)
    replacement = comment_lines(description, indent)
    document.lines[block.start : block.header] = replacement
    document.changed = True
    return True


def measure_property(document: TmdlDocument, block: TmdlBlock, property_name: str) -> str | None:
    prefix = f"{property_name}:"
    for line in document.lines[block.header + 1 : block.end]:
        stripped = line.strip()
        if stripped.startswith(prefix):
            return clean_tmdl_value(stripped.split(":", 1)[1])
    return None


def set_measure_property(document: TmdlDocument, block: TmdlBlock, property_name: str, value: str) -> bool:
    prefix = f"{property_name}:"
    property_indent = "\t\t"
    lineage_index: int | None = None
    first_annotation_index: int | None = None
    for index in range(block.header + 1, block.end):
        stripped = document.lines[index].strip()
        if stripped.startswith(prefix):
            indent = re.match(r"^(\s*)", document.lines[index]).group(1)
            document.lines[index] = f"{indent}{property_name}: {value}"
            document.changed = True
            return True
        if stripped.startswith("lineageTag:") and lineage_index is None:
            lineage_index = index
            property_indent = re.match(r"^(\s*)", document.lines[index]).group(1)
        if stripped.startswith("annotation ") and first_annotation_index is None:
            first_annotation_index = index

    insert_index = lineage_index if lineage_index is not None else first_annotation_index
    if insert_index is None:
        return False
    document.lines.insert(insert_index, f"{property_indent}{property_name}: {value}")
    document.changed = True
    return True


def column_hidden(document: TmdlDocument, block: TmdlBlock) -> bool:
    return any(line.strip() == "isHidden" for line in document.lines[block.header + 1 : block.end])


def set_column_hidden(document: TmdlDocument, block: TmdlBlock, value: bool) -> bool:
    for index in range(block.header + 1, block.end):
        if document.lines[index].strip() == "isHidden":
            if value:
                return True
            del document.lines[index]
            document.changed = True
            return True
    if not value:
        return True

    data_type_index: int | None = None
    insert_indent = "\t\t"
    for index in range(block.header + 1, block.end):
        stripped = document.lines[index].strip()
        if stripped.startswith("dataType:"):
            data_type_index = index + 1
            insert_indent = re.match(r"^(\s*)", document.lines[index]).group(1)
            break
    if data_type_index is None:
        return False
    document.lines.insert(data_type_index, f"{insert_indent}isHidden")
    document.changed = True
    return True


def operation_label(operation: dict[str, Any]) -> str:
    operation_name = operation.get("operation")
    proposed = operation.get("proposed")
    if operation_name == "set_measure_format":
        return f"{operation.get('measure')}: formatString -> {proposed}"
    if operation_name == "set_measure_display_folder":
        return f"{operation.get('measure')}: displayFolder -> {proposed}"
    if operation_name == "set_measure_description":
        return f"{operation.get('measure')}: description -> {proposed}"
    if operation_name == "set_table_description":
        return f"{operation.get('table')}: description -> {proposed}"
    if operation_name == "set_column_description":
        return f"{operation.get('table')}.{operation.get('column')}: description -> {proposed}"
    if operation_name == "set_column_hidden":
        return f"{operation.get('table')}.{operation.get('column')}: isHidden -> {proposed}"
    return str(operation_name or "unknown operation")


def skipped_operation(item: str, reason: str) -> dict[str, str]:
    return {"item": item, "reason": reason}


def current_matches(operation_name: str, actual: Any, expected: Any) -> bool:
    if operation_name in {"set_measure_description", "set_table_description", "set_column_description"}:
        return normalize_text(str(actual or "")) == normalize_text(str(expected or ""))
    return actual == expected


def already_applied(operation_name: str, actual: Any, proposed: Any) -> bool:
    if operation_name in {"set_measure_description", "set_table_description", "set_column_description"}:
        return normalize_text(str(actual or "")) == normalize_text(str(proposed or ""))
    return actual == proposed


def resolve_operation_target(
    documents: DefinitionDocuments,
    operation: dict[str, Any],
) -> tuple[TmdlDocument | None, TmdlBlock | None, Any, str | None]:
    operation_name = operation.get("operation")
    table_name = operation.get("table")
    if not table_name:
        return None, None, None, "operation is missing `table`"
    document, error = documents.table_document(str(table_name))
    if error or document is None:
        return None, None, None, error

    if operation_name == "set_table_description":
        block, error = document.unique_block("table", str(table_name))
        if error or block is None:
            return document, None, None, error
        return document, block, read_description(document, block), None

    if operation_name in MEASURE_PROPERTY_OPERATIONS or operation_name == "set_measure_description":
        measure_name = operation.get("measure")
        if not measure_name:
            return document, None, None, "measure operation is missing `measure`"
        block, error = document.unique_block("measure", str(measure_name))
        if error or block is None:
            return document, None, None, error
        if operation_name == "set_measure_description":
            return document, block, read_description(document, block), None
        property_name, _ = MEASURE_PROPERTY_OPERATIONS[str(operation_name)]
        return document, block, measure_property(document, block, property_name), None

    if operation_name in {"set_column_description", "set_column_hidden"}:
        column_name = operation.get("column")
        if not column_name:
            return document, None, None, "column operation is missing `column`"
        block, error = document.unique_block("column", str(column_name))
        if error or block is None:
            return document, None, None, error
        if operation_name == "set_column_description":
            return document, block, read_description(document, block), None
        return document, block, column_hidden(document, block), None

    return document, None, None, f"operation `{operation_name}` is outside the safe patch scope"


def validate_operations(
    documents: DefinitionDocuments,
    patch: dict[str, Any],
    result: PatchApplyResult,
) -> list[PreparedOperation]:
    prepared: list[PreparedOperation] = []
    for skipped in patch.get("skipped", []):
        item = str(skipped.get("item") or "skipped patch item")
        reason = str(skipped.get("reason") or "outside the safe patch scope")
        result.skipped.append(skipped_operation(item, reason))

    for operation in patch.get("operations", []):
        operation_name = operation.get("operation")
        label = operation_label(operation)
        if operation_name not in ALLOWED_OPERATIONS:
            reason = "structural changes are outside the safe patch scope"
            if "relationship" not in str(operation_name or "").lower():
                reason = "operation is outside the safe metadata patch scope"
            result.skipped.append(skipped_operation(label, reason))
            continue

        _document, _block, actual, error = resolve_operation_target(documents, operation)
        if error:
            result.failures.append(f"{label}: {error}")
            continue

        proposed = operation.get("proposed")
        if already_applied(str(operation_name), actual, proposed):
            result.skipped.append(skipped_operation(label, "already set"))
            continue
        if "current" in operation and not current_matches(str(operation_name), actual, operation.get("current")):
            result.failures.append(
                f"{label}: expected current value {operation.get('current')!r}, found {actual!r}"
            )
            continue
        prepared.append(PreparedOperation(operation=operation, label=label))
    return prepared


def apply_prepared_operations(
    documents: DefinitionDocuments,
    prepared: list[PreparedOperation],
    result: PatchApplyResult,
) -> None:
    for item in prepared:
        operation = item.operation
        operation_name = str(operation.get("operation"))
        document, block, actual, error = resolve_operation_target(documents, operation)
        if error or document is None or block is None:
            result.failures.append(f"{item.label}: {error or 'target disappeared after copy'}")
            continue
        proposed = operation.get("proposed")
        if already_applied(operation_name, actual, proposed):
            result.skipped.append(skipped_operation(item.label, "already set"))
            continue

        changed = False
        if operation_name == "set_measure_description":
            changed = set_description(document, block, str(proposed))
        elif operation_name == "set_table_description":
            changed = set_description(document, block, str(proposed))
        elif operation_name == "set_column_description":
            changed = set_description(document, block, str(proposed))
        elif operation_name in MEASURE_PROPERTY_OPERATIONS:
            property_name, _ = MEASURE_PROPERTY_OPERATIONS[operation_name]
            changed = set_measure_property(document, block, property_name, str(proposed))
        elif operation_name == "set_column_hidden":
            changed = set_column_hidden(document, block, bool(proposed))

        if changed:
            result.applied.append(item.label)
        else:
            result.skipped.append(skipped_operation(item.label, "target block could not be modified safely"))
    documents.write_changed()


def relationship_bytes(definition_dir: Path) -> bytes:
    path = definition_dir / "relationships.tmdl"
    return path.read_bytes() if path.exists() else b""


def partition_blocks(definition_dir: Path) -> dict[tuple[str, str], str]:
    documents = DefinitionDocuments.load(definition_dir)
    blocks: dict[tuple[str, str], str] = {}
    for table_name, table_docs in documents.tables.items():
        for document in table_docs:
            for partition_name, matches in document.blocks()["partition"].items():
                for index, block in enumerate(matches):
                    key = (table_name, partition_name if len(matches) == 1 else f"{partition_name}#{index}")
                    blocks[key] = document.block_text(block)
    return blocks


def lineage_snapshot(semantics: dict[str, Any]) -> dict[tuple[str, ...], Any]:
    snapshot: dict[tuple[str, ...], Any] = {}
    for table_name, table in semantics.get("tables", {}).items():
        snapshot[("table", table_name)] = table.get("lineage_tag")
        for measure_name, measure in table.get("measures", {}).items():
            snapshot[("measure", table_name, measure_name)] = measure.get("lineage_tag")
        for column_name, column in table.get("columns", {}).items():
            snapshot[("column", table_name, column_name)] = column.get("lineage_tag")
    return snapshot


def measure_expression_snapshot(semantics: dict[str, Any]) -> dict[tuple[str, str], str]:
    snapshot: dict[tuple[str, str], str] = {}
    for table_name, table in semantics.get("tables", {}).items():
        for measure_name, measure in table.get("measures", {}).items():
            snapshot[(table_name, measure_name)] = normalize_expression(measure.get("expression"))
    return snapshot


def count_snapshot(semantics: dict[str, Any]) -> dict[str, Any]:
    tables = semantics.get("tables", {})
    return {
        "tables": set(tables),
        "columns": {table: set(data.get("columns", {})) for table, data in tables.items()},
        "measures": {table: set(data.get("measures", {})) for table, data in tables.items()},
    }


def capture_protected_snapshot(definition_dir: Path) -> ProtectedSnapshot:
    return ProtectedSnapshot(
        semantics=parse_tmdl_definition(definition_dir, definition_dir),
        relationships=relationship_bytes(definition_dir),
        partitions=partition_blocks(definition_dir),
    )


def validate_protected_properties(source: ProtectedSnapshot, target_dir: Path, result: PatchApplyResult) -> None:
    target = parse_tmdl_definition(target_dir, target_dir)

    source_counts = count_snapshot(source.semantics)
    target_counts = count_snapshot(target)
    if source_counts["tables"] != target_counts["tables"] or source_counts["columns"] != target_counts["columns"]:
        result.failures.append("protected check failed: table and column counts changed")
    if source_counts["measures"] != target_counts["measures"]:
        result.failures.append("protected check failed: measure counts changed")

    if measure_expression_snapshot(source.semantics) != measure_expression_snapshot(target):
        result.failures.append("protected check failed: DAX expressions changed")

    if lineage_snapshot(source.semantics) != lineage_snapshot(target):
        result.failures.append("protected check failed: lineage tags changed")

    if source.relationships != relationship_bytes(target_dir):
        result.failures.append("protected check failed: relationship definitions changed")

    if source.partitions != partition_blocks(target_dir):
        result.failures.append("protected check failed: partition definitions changed")


def render_report(result: PatchApplyResult) -> str:
    lines = ["# Power BI Patch Result", ""]
    lines.extend(["Applied:"])
    if result.applied:
        lines.extend(f"- {item}" for item in result.applied)
    else:
        lines.append("- None.")

    lines.extend(["", "Skipped:"])
    if result.skipped:
        for item in result.skipped:
            lines.append(f"- {item['item']}")
            lines.append(f"  Reason: {item['reason']}")
    else:
        lines.append("- None.")

    if result.failures:
        lines.extend(["", "Failed:"])
        lines.extend(f"- {failure}" for failure in result.failures)

    lines.extend(["", "Protected properties:"])
    for check in result.protected_checks:
        lines.append(f"- {check}")
    lines.append("")
    lines.append(f"Output: `{relative_posix(result.output_dir)}`")
    lines.append(f"Status: {'success' if result.success else 'failed'}")
    lines.append("")
    return "\n".join(lines)


def write_report(result: PatchApplyResult) -> None:
    result.report_path.parent.mkdir(parents=True, exist_ok=True)
    result.report_path.write_text(render_report(result), encoding="utf-8", newline="\n")


def prepare_output_dir(definition_dir: Path, output_dir: Path, *, in_place: bool, confirm_in_place: bool) -> tuple[Path, str | None]:
    if in_place and not confirm_in_place:
        return definition_dir, "--in-place requires --confirm-in-place"
    if in_place:
        return definition_dir, None
    if output_dir.resolve() == definition_dir.resolve():
        return output_dir, "--output-dir must differ from --definition-dir unless confirmed in-place mode is used"
    if output_dir.exists():
        return output_dir, f"output directory already exists: {output_dir}"
    return output_dir, None


def apply_powerbi_patch(
    *,
    definition_dir: Path,
    patch_path: Path,
    output_dir: Path,
    in_place: bool = False,
    confirm_in_place: bool = False,
) -> PatchApplyResult:
    definition_dir = definition_dir.resolve()
    patch_path = patch_path.resolve()
    output_dir = output_dir.resolve()
    report_path = patch_path.parent / "powerbi_patch_result.md"
    target_dir, output_error = prepare_output_dir(
        definition_dir,
        output_dir,
        in_place=in_place,
        confirm_in_place=confirm_in_place,
    )
    result = PatchApplyResult(success=False, output_dir=target_dir, report_path=report_path)

    if output_error:
        result.failures.append(output_error)
        write_report(result)
        return result
    if not definition_dir.is_dir() or not (definition_dir / "tables").is_dir():
        result.failures.append(f"definition folder is missing or incomplete: {definition_dir}")
        write_report(result)
        return result
    if not patch_path.is_file():
        result.failures.append(f"patch file is missing: {patch_path}")
        write_report(result)
        return result

    patch = load_json(patch_path)
    source_documents = DefinitionDocuments.load(definition_dir)
    protected_snapshot = capture_protected_snapshot(definition_dir)
    prepared = validate_operations(source_documents, patch, result)
    if result.failures:
        write_report(result)
        return result

    copied = False
    try:
        if not in_place:
            shutil.copytree(definition_dir, target_dir)
            copied = True
        target_documents = DefinitionDocuments.load(target_dir)
        apply_prepared_operations(target_documents, prepared, result)
        if result.failures:
            raise RuntimeError("patch application failed")
        validate_protected_properties(protected_snapshot, target_dir, result)
        if result.failures:
            raise RuntimeError("protected property validation failed")
        result.success = True
    except Exception as exc:  # pragma: no cover - defensive cleanup around file-system operations.
        if not result.failures:
            result.failures.append(str(exc))
        if copied and target_dir.exists():
            shutil.rmtree(target_dir)
    finally:
        write_report(result)
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a safe Power BI TMDL metadata patch to a copied definition folder.")
    parser.add_argument("--definition-dir", required=True, help="Source Power BI SemanticModel definition folder.")
    parser.add_argument("--patch", required=True, help="Patch JSON generated by the semantic POC.")
    parser.add_argument("--output-dir", help="Copied output definition folder. Required unless --in-place is used.")
    parser.add_argument("--in-place", action="store_true", help="Modify --definition-dir directly. Requires --confirm-in-place.")
    parser.add_argument(
        "--confirm-in-place",
        action="store_true",
        help="Required confirmation when --in-place is used.",
    )
    args = parser.parse_args(argv)
    if not args.in_place and not args.output_dir:
        parser.error("--output-dir is required unless --in-place is used")
    if args.in_place and not args.confirm_in_place:
        parser.error("--in-place requires --confirm-in-place")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    definition_dir = Path(args.definition_dir)
    output_dir = Path(args.output_dir) if args.output_dir else definition_dir
    result = apply_powerbi_patch(
        definition_dir=definition_dir,
        patch_path=Path(args.patch),
        output_dir=output_dir,
        in_place=args.in_place,
        confirm_in_place=args.confirm_in_place,
    )
    print(f"Power BI patch {'applied' if result.success else 'failed'}")
    print(f"Report: {relative_posix(result.report_path)}")
    print(f"Output: {relative_posix(result.output_dir)}")
    if result.failures:
        print("Failures:", file=sys.stderr)
        for failure in result.failures:
            print(f"- {failure}", file=sys.stderr)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
