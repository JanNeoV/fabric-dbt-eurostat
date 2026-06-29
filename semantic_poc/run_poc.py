from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from semantic_poc.src.models import (  # noqa: E402
    CANONICAL_SOURCE,
    COMPATIBILITY_OUTPUT,
    DBT_OUTPUT,
    DBT_SEMANTIC_MANIFEST,
    DBT_SEMANTIC_YAML,
    GENERATED_NOTICE,
    OUTPUT_DIR,
    PBI_DEFINITION_DIR,
    POWERBI_OUTPUT,
    POWERBI_PATCH_OUTPUT,
    REQUIRED_PUBLIC_METRICS,
    SNOWFLAKE_ENVIRONMENT,
    SNOWFLAKE_OUTPUT,
    STATUS_DEFINITION_DRIFT,
    STATUS_MANUAL_REVIEW_REQUIRED,
    STATUS_MATCH,
    STATUS_METADATA_DRIFT,
    STATUS_MISSING_IN_DBT,
    STATUS_MISSING_IN_POWER_BI,
    STATUS_UNSUPPORTED_IN_SNOWFLAKE,
    build_snowflake_semantic_view,
    compare_semantics,
    generate_powerbi_patch,
    load_json,
    load_yaml,
    normalize_dbt_semantics,
    parse_tmdl_definition,
    public_metric_names,
    relative_posix,
    render_compatibility_markdown,
    normalize_snowflake_environment,
    validate_dbt_semantics,
    write_json,
    write_yaml,
)


REQUIRED_SNOWFLAKE_ENV_FIELDS = ["database", "mart_schema", "semantic_schema", "semantic_view_name"]
OUTPUT_FILENAMES = [
    "dbt_semantics.json",
    "powerbi_semantics.json",
    "proposed_powerbi_patch.json",
    "snowflake_semantic_view.yml",
    "semantic_compatibility.md",
]


class PocError(RuntimeError):
    pass


class PocValidationError(PocError):
    pass


class PocCommandError(PocError):
    pass


@dataclass(frozen=True)
class PocPaths:
    repo_root: Path
    dbt_project_dir: Path
    dbt_semantic_yaml: Path
    semantic_manifest: Path
    powerbi_definition_dir: Path
    snowflake_environment: Path
    output_dir: Path

    @property
    def dbt_output(self) -> Path:
        return self.output_dir / DBT_OUTPUT.name

    @property
    def powerbi_output(self) -> Path:
        return self.output_dir / POWERBI_OUTPUT.name

    @property
    def powerbi_patch_output(self) -> Path:
        return self.output_dir / POWERBI_PATCH_OUTPUT.name

    @property
    def snowflake_output(self) -> Path:
        return self.output_dir / SNOWFLAKE_OUTPUT.name

    @property
    def compatibility_output(self) -> Path:
        return self.output_dir / COMPATIBILITY_OUTPUT.name

    @property
    def output_files(self) -> list[Path]:
        return [
            self.dbt_output,
            self.powerbi_output,
            self.powerbi_patch_output,
            self.snowflake_output,
            self.compatibility_output,
        ]


@dataclass(frozen=True)
class PocRunResult:
    paths: PocPaths
    dbt_semantics: dict
    powerbi: dict
    snowflake: dict
    comparison: dict
    summary: dict[str, int]


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    search_roots = [current] if current.is_dir() else [current.parent]
    search_roots.extend(search_roots[0].parents)
    for candidate in search_roots:
        if (candidate / "dbt_project.yml").exists() and (candidate / "semantic_poc").is_dir():
            return candidate
    raise PocValidationError(
        "Repository root could not be found.\n"
        f"Checked path: {current}\n"
        "Fix: run this command from a clone of the repository or keep semantic_poc inside the project root."
    )


def resolve_cli_path(value: str | None, default: Path) -> Path:
    if value is None:
        return default.resolve()
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def build_paths(args: argparse.Namespace) -> PocPaths:
    repo_root = find_repo_root()
    dbt_project_dir = resolve_cli_path(args.dbt_project_dir, repo_root)
    output_dir = resolve_cli_path(args.output_dir, OUTPUT_DIR)
    powerbi_definition_dir = resolve_cli_path(args.powerbi_definition_dir, PBI_DEFINITION_DIR)
    return PocPaths(
        repo_root=repo_root,
        dbt_project_dir=dbt_project_dir,
        dbt_semantic_yaml=(dbt_project_dir / DBT_SEMANTIC_YAML.relative_to(REPO_ROOT)).resolve(),
        semantic_manifest=(dbt_project_dir / DBT_SEMANTIC_MANIFEST.relative_to(REPO_ROOT)).resolve(),
        powerbi_definition_dir=powerbi_definition_dir,
        snowflake_environment=SNOWFLAKE_ENVIRONMENT.resolve(),
        output_dir=output_dir,
    )


def display_path(path: Path, root: Path) -> str:
    return relative_posix(path, root)


def validation_error(missing: str, path: Path, fix: str, root: Path) -> PocValidationError:
    return PocValidationError(
        f"{missing}\nChecked path: {display_path(path, root)}\nFix: {fix}"
    )


def require_file(path: Path, label: str, fix: str, root: Path) -> None:
    if not path.is_file():
        raise validation_error(f"{label} is missing.", path, fix, root)


def require_dir(path: Path, label: str, fix: str, root: Path) -> None:
    if not path.is_dir():
        raise validation_error(f"{label} is missing.", path, fix, root)


def validate_output_dir(paths: PocPaths) -> None:
    try:
        paths.output_dir.mkdir(parents=True, exist_ok=True)
        probe = paths.output_dir / ".write_test.tmp"
        probe.write_text("ok\n", encoding="utf-8", newline="\n")
        probe.unlink()
    except OSError as exc:
        raise validation_error(
            f"Output directory is not writable: {exc}",
            paths.output_dir,
            "Choose a writable --output-dir or fix permissions on the existing directory.",
            paths.repo_root,
        ) from exc


def validate_static_inputs(paths: PocPaths) -> None:
    require_dir(
        paths.dbt_project_dir,
        "dbt project directory",
        "Pass --dbt-project-dir pointing at the repository root or a dbt project clone.",
        paths.repo_root,
    )
    require_file(
        paths.dbt_semantic_yaml,
        "Canonical dbt semantic YAML",
        "Restore models/semantic/triathlon_semantic.yml or pass --dbt-project-dir for the project that contains it.",
        paths.repo_root,
    )
    require_dir(
        paths.powerbi_definition_dir,
        "Power BI semantic model definition folder",
        "Restore pbi/triathlon_pbi_model.SemanticModel/definition or pass --powerbi-definition-dir.",
        paths.repo_root,
    )
    require_dir(
        paths.powerbi_definition_dir / "tables",
        "Power BI TMDL tables folder",
        "Export the PBIP semantic model definition with its definition/tables folder intact.",
        paths.repo_root,
    )
    require_file(
        paths.snowflake_environment,
        "Snowflake environment config",
        "Restore semantic_poc/config/snowflake_environment.yml with database, mart_schema, semantic_schema, and semantic_view_name.",
        paths.repo_root,
    )
    validate_output_dir(paths)


def run_dbt_parse(paths: PocPaths) -> None:
    command = ["dbt", "--no-version-check", "parse"]
    try:
        completed = subprocess.run(command, cwd=paths.dbt_project_dir)
    except FileNotFoundError as exc:
        raise PocCommandError(
            "dbt executable is missing.\n"
            f"Checked path: {display_path(paths.dbt_project_dir, paths.repo_root)}\n"
            'Fix: install dbt dependencies with `python -m pip install -e ".[dbt]"`, '
            "then ensure `dbt` is on PATH."
        ) from exc
    if completed.returncode != 0:
        raise PocCommandError(
            "dbt parse failed.\n"
            f"Checked path: {display_path(paths.dbt_project_dir, paths.repo_root)}\n"
            "Fix: check that dbt is installed, the project profile is configured, and `dbt --no-version-check parse` succeeds."
        )


def load_snowflake_environment(paths: PocPaths) -> dict:
    environment = normalize_snowflake_environment(load_yaml(paths.snowflake_environment) or {})
    missing_fields = [field for field in REQUIRED_SNOWFLAKE_ENV_FIELDS if not environment.get(field)]
    if missing_fields:
        raise validation_error(
            f"Snowflake environment fields are missing: {', '.join(missing_fields)}.",
            paths.snowflake_environment,
            "Add values for database, mart_schema, semantic_schema, and semantic_view_name.",
            paths.repo_root,
        )
    return environment


def validate_public_metric_set(dbt_yaml: dict, paths: PocPaths) -> None:
    public_names = public_metric_names(dbt_yaml)
    if public_names == REQUIRED_PUBLIC_METRICS:
        return
    missing = [name for name in REQUIRED_PUBLIC_METRICS if name not in public_names]
    unexpected = [name for name in public_names if name not in REQUIRED_PUBLIC_METRICS]
    details = []
    if missing:
        details.append(f"missing: {', '.join(missing)}")
    if unexpected:
        details.append(f"unexpected: {', '.join(unexpected)}")
    if not details:
        details.append("order differs from the expected public metric list")
    raise validation_error(
        f"Public metric set does not match the expected POC contract ({'; '.join(details)}).",
        paths.dbt_semantic_yaml,
        "Mark exactly the expected seven metrics public in config.meta.semantic_contract, or update REQUIRED_PUBLIC_METRICS with the intentional contract change.",
        paths.repo_root,
    )


def validate_public_metric_mappings(dbt_yaml: dict, paths: PocPaths) -> None:
    metrics = {metric["name"]: metric for metric in dbt_yaml.get("metrics", [])}
    errors: list[str] = []
    for name in REQUIRED_PUBLIC_METRICS:
        metric = metrics.get(name, {})
        meta = metric.get("config", {}).get("meta", {}) or {}
        power_bi = meta.get("power_bi", {}) or {}
        snowflake = meta.get("snowflake", {}) or {}
        if not power_bi.get("table") or not power_bi.get("measure"):
            errors.append(f"{name} missing power_bi.table or power_bi.measure")
        if not snowflake.get("logical_table") or not snowflake.get("metric_name"):
            errors.append(f"{name} missing snowflake.logical_table or snowflake.metric_name")
    if errors:
        raise validation_error(
            "Public metric mappings are incomplete: " + "; ".join(errors) + ".",
            paths.dbt_semantic_yaml,
            "Add Power BI and Snowflake mappings under each public metric's config.meta block.",
            paths.repo_root,
        )


def validate_manifest_metrics(semantic_manifest: dict, paths: PocPaths) -> None:
    metrics_by_name = {metric["name"] for metric in semantic_manifest.get("metrics", [])}
    missing = [name for name in REQUIRED_PUBLIC_METRICS if name not in metrics_by_name]
    if missing:
        raise validation_error(
            f"Expected public metrics are missing from target/semantic_manifest.json: {', '.join(missing)}.",
            paths.semantic_manifest,
            "Run `dbt --no-version-check parse` and fix any dbt semantic validation errors.",
            paths.repo_root,
        )


def load_validated_semantics(paths: PocPaths) -> tuple[dict, dict]:
    require_file(
        paths.semantic_manifest,
        "dbt semantic manifest",
        "Run without --skip-dbt-parse, or run `dbt --no-version-check parse` before the POC.",
        paths.repo_root,
    )
    dbt_yaml = load_yaml(paths.dbt_semantic_yaml)
    semantic_manifest = load_json(paths.semantic_manifest)
    validate_public_metric_set(dbt_yaml, paths)
    validate_public_metric_mappings(dbt_yaml, paths)
    validate_manifest_metrics(semantic_manifest, paths)
    environment = load_snowflake_environment(paths)
    try:
        dbt_semantics = normalize_dbt_semantics(
            semantic_manifest,
            dbt_yaml,
            semantic_yaml_path=paths.dbt_semantic_yaml,
            semantic_manifest_path=paths.semantic_manifest,
            project_root=paths.repo_root,
        )
    except ValueError as exc:
        raise validation_error(
            f"dbt semantic contract validation failed: {exc}",
            paths.dbt_semantic_yaml,
            "Run `dbt --no-version-check parse`, then make the public metric contract and manifest agree.",
            paths.repo_root,
        ) from exc
    semantic_errors = validate_dbt_semantics(dbt_semantics)
    if semantic_errors:
        raise validation_error(
            "dbt semantic contract validation failed: " + "; ".join(semantic_errors) + ".",
            paths.dbt_semantic_yaml,
            "Complete the missing public metric mappings and rate metadata in config.meta.",
            paths.repo_root,
        )
    return dbt_semantics, environment


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def generate_outputs(paths: PocPaths, dbt_semantics: dict, environment: dict) -> PocRunResult:
    canonical_source = dbt_semantics.get("canonical_source", CANONICAL_SOURCE)
    compiled_source = dbt_semantics.get("compiled_source", "target/semantic_manifest.json")
    powerbi = parse_tmdl_definition(paths.powerbi_definition_dir, paths.repo_root)
    patch = generate_powerbi_patch(dbt_semantics, powerbi)
    snowflake = build_snowflake_semantic_view(dbt_semantics, environment)
    comparison = compare_semantics(dbt_semantics, powerbi, snowflake)

    write_json(paths.dbt_output, dbt_semantics, generated=True, canonical_source=canonical_source)
    write_json(paths.powerbi_output, powerbi, generated=True, canonical_source=canonical_source)
    write_json(paths.powerbi_patch_output, patch, generated=True, canonical_source=canonical_source)
    write_yaml(paths.snowflake_output, snowflake, generated=True, canonical_source=canonical_source)
    write_markdown(
        paths.compatibility_output,
        render_compatibility_markdown(comparison, canonical_source, compiled_source),
    )

    return PocRunResult(
        paths=paths,
        dbt_semantics=dbt_semantics,
        powerbi=powerbi,
        snowflake=snowflake,
        comparison=comparison,
        summary=build_summary(dbt_semantics, comparison),
    )


def build_summary(dbt_semantics: dict, comparison: dict) -> dict[str, int]:
    status_counts = Counter(row["status"] for row in comparison.get("rows", []))
    relationship_drift = len(comparison.get("findings", {}).get("relationship_drift", []))
    manual_statuses = {
        STATUS_MANUAL_REVIEW_REQUIRED,
        STATUS_MISSING_IN_DBT,
        STATUS_MISSING_IN_POWER_BI,
        STATUS_UNSUPPORTED_IN_SNOWFLAKE,
    }
    manual_review = relationship_drift + sum(
        1 for row in comparison.get("rows", []) if row["status"] in manual_statuses
    )
    return {
        "Public metrics": len(dbt_semantics.get("public_metrics", [])),
        "Matches": status_counts[STATUS_MATCH],
        "Metadata drift": status_counts[STATUS_METADATA_DRIFT],
        "Definition drift": status_counts[STATUS_DEFINITION_DRIFT],
        "Structural drift": relationship_drift,
        "Manual review required": manual_review,
    }


def strict_failures(result: PocRunResult, *, strict: bool, fail_on_metadata_drift: bool) -> list[str]:
    rows = result.comparison.get("rows", [])
    findings = result.comparison.get("findings", {})
    failures: list[str] = []
    if strict:
        missing = [
            row["metric"]
            for row in rows
            if row["status"] in {STATUS_MISSING_IN_DBT, STATUS_MISSING_IN_POWER_BI}
        ]
        if missing:
            failures.append("public metrics are missing from a platform: " + ", ".join(missing))
        definition_drift = findings.get("power_bi_definition_drift", [])
        if definition_drift:
            failures.append("Power BI definition drift exists")
        relationship_drift = findings.get("relationship_drift", [])
        if relationship_drift:
            failures.append("structural relationship drift exists")
        unsupported = findings.get("unsupported_translation", [])
        if unsupported:
            failures.append("Snowflake generation reported unsupported public metrics")
    metadata_drift = result.summary.get("Metadata drift", 0)
    if fail_on_metadata_drift and metadata_drift:
        failures.append("Power BI metadata drift exists")
    return failures


def format_summary(result: PocRunResult) -> str:
    lines = ["Semantic POC completed", ""]
    for label, value in result.summary.items():
        lines.append(f"{label + ':':<28}{value}")
    lines.extend(["", "Outputs:"])
    for path in result.paths.output_files:
        lines.append(f"- {display_path(path, result.paths.repo_root)}")
    return "\n".join(lines)


def run_poc(paths: PocPaths, *, skip_dbt_parse: bool) -> PocRunResult:
    validate_static_inputs(paths)
    if not skip_dbt_parse:
        run_dbt_parse(paths)
    dbt_semantics, environment = load_validated_semantics(paths)
    return generate_outputs(paths, dbt_semantics, environment)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the semantic contract POC.")
    parser.add_argument("--skip-dbt-parse", action="store_true", help="Use the existing target/semantic_manifest.json.")
    parser.add_argument("--dbt-project-dir", help="dbt project directory. Defaults to the repository root.")
    parser.add_argument(
        "--powerbi-definition-dir",
        help="Power BI SemanticModel definition directory. Defaults to pbi/triathlon_pbi_model.SemanticModel/definition.",
    )
    parser.add_argument("--output-dir", help="Output directory. Defaults to semantic_poc/output.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on missing public metrics, definition drift, structural drift, or unsupported Snowflake public metrics.",
    )
    parser.add_argument(
        "--fail-on-metadata-drift",
        action="store_true",
        help="Fail when Power BI metadata drift exists.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        paths = build_paths(args)
        result = run_poc(paths, skip_dbt_parse=args.skip_dbt_parse)
        print(format_summary(result))
        failures = strict_failures(
            result,
            strict=args.strict,
            fail_on_metadata_drift=args.fail_on_metadata_drift,
        )
        if failures:
            print("\nStrict checks failed:", file=sys.stderr)
            for failure in failures:
                print(f"- {failure}", file=sys.stderr)
            return 1
        return 0
    except PocError as exc:
        print("Semantic POC failed\n", file=sys.stderr)
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
