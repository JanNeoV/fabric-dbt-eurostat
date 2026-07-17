from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml

from semantic_poc.src.models import DBT_SEMANTIC_MANIFEST, DBT_SEMANTIC_YAML, PBI_DEFINITION_DIR, STATUS_MANUAL_REVIEW_REQUIRED

from .inspection import MetricAmbiguousError, MetricInspectionError, MetricNotFoundError, inspect_metric


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="semantic-agent", description="Controlled semantic contract workflow.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="Inspect a canonical or exactly mapped metric name.")
    inspect_parser.add_argument("metric", help="Canonical dbt metric, Power BI measure, or Snowflake metric name.")
    inspect_parser.add_argument("--json", action="store_true", help="Write structured JSON output.")
    inspect_parser.add_argument("--semantic-yaml", default=str(DBT_SEMANTIC_YAML), help="Canonical semantic YAML path.")
    inspect_parser.add_argument("--manifest", default=str(DBT_SEMANTIC_MANIFEST), help="Compiled dbt semantic manifest path.")
    inspect_parser.add_argument(
        "--powerbi-definition-dir",
        default=str(PBI_DEFINITION_DIR),
        help="Power BI SemanticModel definition directory.",
    )
    return parser


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2))


def _print_human(data: dict[str, Any]) -> None:
    canonical = data["canonical"]
    power_bi = data["mappings"]["power_bi"]
    snowflake = data["mappings"]["snowflake"]
    print(f"Canonical metric: {canonical['name']}")
    print(f"Canonical source: {canonical['file']}")
    print(f"Resolved from: {data['resolved_from']}")
    print(f"Metric type: {canonical.get('type')}")
    print(f"Translation pattern: {data.get('translation_pattern')}")
    print(f"Power BI mapping: {power_bi.get('table')}.{power_bi.get('measure')}")
    print(f"Power BI target exists: {power_bi.get('exists')}")
    print(f"Snowflake mapping: {snowflake.get('logical_table')}.{snowflake.get('metric_name')}")
    print(f"Snowflake generated: {snowflake.get('generated')}")
    print(f"Compatibility status: {data.get('compatibility_status')}")
    if power_bi.get("actual_dax"):
        print(f"Actual DAX: {power_bi['actual_dax']}")
    for diagnostic in data.get("diagnostics", []):
        print(f"Diagnostic: {diagnostic}")


def _print_error(error: MetricInspectionError, *, as_json: bool) -> None:
    if as_json:
        _print_json(error.to_dict())
    else:
        print(f"{error.code}: {error}", file=sys.stderr)
        if error.candidates:
            print("Candidates: " + ", ".join(error.candidates), file=sys.stderr)


def run_inspect(args: argparse.Namespace) -> int:
    try:
        result = inspect_metric(
            args.metric,
            semantic_yaml_path=Path(args.semantic_yaml),
            manifest_path=Path(args.manifest),
            powerbi_definition_dir=Path(args.powerbi_definition_dir),
        )
    except MetricNotFoundError as exc:
        _print_error(exc, as_json=args.json)
        return 2
    except (MetricAmbiguousError, MetricInspectionError) as exc:
        _print_error(exc, as_json=args.json)
        return 3
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        error = MetricInspectionError(
            f"Inspection input could not be read or parsed: {exc}",
            requested_metric=args.metric,
        )
        _print_error(error, as_json=args.json)
        return 3
    if args.json:
        _print_json(result)
    else:
        _print_human(result)
    return 3 if result["compatibility_status"] == STATUS_MANUAL_REVIEW_REQUIRED else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "inspect":
        return run_inspect(args)
    raise AssertionError(f"Unhandled command: {args.command}")
