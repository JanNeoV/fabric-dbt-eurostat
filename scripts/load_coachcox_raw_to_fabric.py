from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import pyodbc
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_seed_artifacts import (
    DEFAULT_SEED_DIR,
    MANIFEST_SEED_NAME,
    RAW_SEED_COLUMNS,
    RAW_SEED_NAME,
    ROOT,
)


DEFAULT_BATCH_SIZE = 5_000
DEFAULT_PROGRESS_ROWS = 100_000
SEED_NODE_ID = "seed.triathlon_analytics.coachcox_results_raw"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk-load the generated CoachCox raw CSV into Fabric."
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_SEED_DIR / RAW_SEED_NAME,
        help=f"Generated raw CSV to load. Default: {DEFAULT_SEED_DIR / RAW_SEED_NAME}",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=ROOT,
        help=f"dbt project directory. Default: {ROOT}",
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=Path.home() / ".dbt",
        help="dbt profiles directory. Default: ~/.dbt",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Optional dbt target override.",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Optional destination schema override.",
    )
    parser.add_argument(
        "--table",
        default=None,
        help="Optional destination table override.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows per pyodbc executemany batch. Default: {DEFAULT_BATCH_SIZE}",
    )
    parser.add_argument(
        "--progress-rows",
        type=int,
        default=DEFAULT_PROGRESS_ROWS,
        help=f"Print progress after this many inserted rows. Default: {DEFAULT_PROGRESS_ROWS}",
    )
    parser.add_argument(
        "--expected-rows",
        type=int,
        default=None,
        help="Expected row count. Defaults to the generated manifest row sum.",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Drop and recreate the destination table before loading.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate the existing destination table before loading.",
    )
    parser.add_argument(
        "--skip-dbt-parse",
        action="store_true",
        help="Skip dbt parse before resolving the seed relation from target/manifest.json.",
    )
    return parser.parse_args()


def quote_identifier(identifier: str) -> str:
    return f"[{identifier.replace(']', ']]')}]"


def qualified_name(schema: str, table: str) -> str:
    return f"{quote_identifier(schema)}.{quote_identifier(table)}"


def sql_nliteral(value: str) -> str:
    return "N'" + value.replace("'", "''") + "'"


def project_config(project_dir: Path) -> dict:
    with (project_dir / "dbt_project.yml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def raw_seed_column_types(project_dir: Path) -> dict[str, str]:
    config = project_config(project_dir)
    project_name = config["name"]
    column_types = (
        config["seeds"][project_name][RAW_SEED_NAME.removesuffix(".csv")]["+column_types"]
    )
    missing = [column for column in RAW_SEED_COLUMNS if column not in column_types]
    if missing:
        raise ValueError(f"Missing dbt seed column types for: {missing}")
    return {column: column_types[column] for column in RAW_SEED_COLUMNS}


def run_dbt_parse(project_dir: Path, profiles_dir: Path, target: str | None) -> None:
    command = [
        "dbt",
        "parse",
        "--quiet",
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(profiles_dir),
    ]
    if target:
        command.extend(["--target", target])

    subprocess.run(command, cwd=project_dir, check=True)


def load_dbt_profile(project_dir: Path, profiles_dir: Path, target: str | None):
    from argparse import Namespace

    from dbt.config.runtime import load_profile
    from dbt.flags import set_from_args

    args = Namespace(
        PROFILES_DIR=str(profiles_dir),
        profiles_dir=str(profiles_dir),
        PROJECT_DIR=str(project_dir),
        project_dir=str(project_dir),
        TARGET=target,
        target=target,
        THREADS=None,
        threads=None,
        VERSION_CHECK=False,
        version_check=False,
    )
    set_from_args(args, {})
    return load_profile(str(project_dir), {}, None, target, None)


def resolve_seed_relation(
    project_dir: Path,
    database: str,
    default_schema: str,
    schema_override: str | None,
    table_override: str | None,
) -> tuple[str, str, str]:
    if schema_override and table_override:
        return database, schema_override, table_override

    manifest_path = project_dir / "target" / "manifest.json"
    if manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        node = manifest.get("nodes", {}).get(SEED_NODE_ID)
        if node:
            return (
                node.get("database") or database,
                schema_override or node["schema"],
                table_override or node.get("alias") or node["name"],
            )

    return (
        database,
        schema_override or f"{default_schema}_source",
        table_override or RAW_SEED_NAME.removesuffix(".csv"),
    )


def connection_string(credentials) -> str:
    from dbt.adapters.fabric.fabric_connection_manager import bool_to_connection_string_arg

    parts = [
        f"DRIVER={{{credentials.driver}}}",
        f"SERVER={credentials.host}",
        f"Database={credentials.database}",
        "Pooling=true",
    ]

    authentication = credentials.authentication
    if "ActiveDirectory" in authentication and authentication != "ActiveDirectoryAccessToken":
        parts.append(f"Authentication={authentication}")
        if authentication == "ActiveDirectoryPassword":
            parts.append(f"UID={{{credentials.UID}}}")
            parts.append(f"PWD={{{credentials.PWD}}}")
        elif authentication == "ActiveDirectoryServicePrincipal":
            parts.append(f"UID={{{credentials.client_id}}}")
            parts.append(f"PWD={{{credentials.client_secret}}}")
        elif authentication == "ActiveDirectoryInteractive":
            parts.append(f"UID={{{credentials.UID}}}")
    elif credentials.windows_login:
        parts.append("trusted_connection=Yes")
    elif authentication == "sql":
        raise ValueError("SQL authentication is not supported by Microsoft Fabric.")

    parts.append(bool_to_connection_string_arg("encrypt", credentials.encrypt))
    parts.append(bool_to_connection_string_arg("TrustServerCertificate", credentials.trust_cert))
    parts.append("APP=coachcox-raw-loader")
    parts.append("ConnectRetryCount=3")
    parts.append("ConnectRetryInterval=10")

    return ";".join(parts)


def connect(credentials) -> pyodbc.Connection:
    from dbt.adapters.fabric.fabric_connection_manager import get_pyodbc_attrs_before_credentials

    return pyodbc.connect(
        connection_string(credentials),
        attrs_before=get_pyodbc_attrs_before_credentials(credentials),
        autocommit=True,
        timeout=credentials.login_timeout,
    )


def is_int_type(data_type: str) -> bool:
    return data_type.lower().strip() in {"int", "integer", "bigint", "smallint", "tinyint"}


def normalize_value(value: str | None, data_type: str) -> object:
    if value is None or value == "":
        return None
    if is_int_type(data_type):
        return int(value)
    return value


def csv_rows(csv_path: Path, column_types: dict[str, str]) -> Iterator[tuple[object, ...]]:
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != RAW_SEED_COLUMNS:
            raise ValueError(
                f"{csv_path} has unexpected columns. "
                f"Expected {RAW_SEED_COLUMNS}, got {reader.fieldnames}."
            )

        for row in reader:
            yield tuple(
                normalize_value(row[column], column_types[column])
                for column in RAW_SEED_COLUMNS
            )


def batched(rows: Iterable[tuple[object, ...]], size: int) -> Iterator[list[tuple[object, ...]]]:
    batch: list[tuple[object, ...]] = []
    for row in rows:
        batch.append(row)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def expected_rows(csv_path: Path, explicit_expected_rows: int | None) -> int:
    if explicit_expected_rows is not None:
        return explicit_expected_rows

    manifest_path = csv_path.parent / MANIFEST_SEED_NAME
    if manifest_path.exists():
        with manifest_path.open("r", newline="", encoding="utf-8") as handle:
            return sum(int(row["source_row_count"]) for row in csv.DictReader(handle))

    with csv_path.open("r", encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def table_exists(cursor: pyodbc.Cursor, schema: str, table: str) -> bool:
    return bool(
        cursor.execute(
            "select case when object_id(?, 'U') is null then 0 else 1 end",
            f"{schema}.{table}",
        ).fetchval()
    )


def prepare_table(
    cursor: pyodbc.Cursor,
    schema: str,
    table: str,
    column_types: dict[str, str],
    full_refresh: bool,
    truncate: bool,
) -> None:
    destination = qualified_name(schema, table)
    create_schema_sql = (
        f"if schema_id({sql_nliteral(schema)}) is null "
        f"exec({sql_nliteral('create schema ' + quote_identifier(schema))})"
    )
    cursor.execute(create_schema_sql)

    exists = table_exists(cursor, schema, table)
    if full_refresh:
        cursor.execute(f"drop table if exists {destination}")
        exists = False
    elif truncate and exists:
        cursor.execute(f"truncate table {destination}")
    elif exists:
        raise RuntimeError(
            f"{destination} already exists. Use --full-refresh or --truncate to reload it."
        )

    if not exists:
        column_sql = ",\n    ".join(
            f"{quote_identifier(column)} {column_types[column]}"
            for column in RAW_SEED_COLUMNS
        )
        cursor.execute(f"create table {destination} (\n    {column_sql}\n)")


def insert_rows(
    cursor: pyodbc.Cursor,
    csv_path: Path,
    schema: str,
    table: str,
    column_types: dict[str, str],
    batch_size: int,
    progress_rows: int,
) -> int:
    destination = qualified_name(schema, table)
    columns_sql = ", ".join(quote_identifier(column) for column in RAW_SEED_COLUMNS)
    placeholders = ", ".join("?" for _ in RAW_SEED_COLUMNS)
    insert_sql = f"insert into {destination} ({columns_sql}) values ({placeholders})"

    cursor.fast_executemany = True
    inserted_rows = 0
    next_progress = progress_rows

    for batch in batched(csv_rows(csv_path, column_types), batch_size):
        cursor.executemany(insert_sql, batch)
        inserted_rows += len(batch)
        if progress_rows > 0 and inserted_rows >= next_progress:
            print(f"Inserted {inserted_rows:,} rows...")
            while inserted_rows >= next_progress:
                next_progress += progress_rows

    return inserted_rows


def table_row_count(cursor: pyodbc.Cursor, schema: str, table: str) -> int:
    return int(cursor.execute(f"select count_big(*) from {qualified_name(schema, table)}").fetchval())


def validate_args(args: argparse.Namespace) -> None:
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be greater than zero.")
    if args.full_refresh and args.truncate:
        raise ValueError("Use either --full-refresh or --truncate, not both.")
    if bool(args.schema) ^ bool(args.table):
        raise ValueError("--schema and --table must be provided together.")
    if not args.csv_path.exists():
        raise FileNotFoundError(f"Raw CSV not found: {args.csv_path}")


def main() -> None:
    args = parse_args()
    validate_args(args)

    project_dir = args.project_dir.resolve()
    profiles_dir = args.profiles_dir.resolve()
    csv_path = args.csv_path.resolve()

    if not args.skip_dbt_parse:
        run_dbt_parse(project_dir, profiles_dir, args.target)

    profile = load_dbt_profile(project_dir, profiles_dir, args.target)
    credentials = profile.credentials
    column_types = raw_seed_column_types(project_dir)
    expected = expected_rows(csv_path, args.expected_rows)
    database, schema, table = resolve_seed_relation(
        project_dir,
        credentials.database,
        credentials.schema,
        args.schema,
        args.table,
    )

    print(f"Loading {csv_path}")
    print(f"Destination: {database}.{schema}.{table}")
    print(f"Expected rows: {expected:,}")

    with connect(credentials) as connection:
        cursor = connection.cursor()
        prepare_table(
            cursor,
            schema,
            table,
            column_types,
            full_refresh=args.full_refresh,
            truncate=args.truncate,
        )
        inserted = insert_rows(
            cursor,
            csv_path,
            schema,
            table,
            column_types,
            batch_size=args.batch_size,
            progress_rows=args.progress_rows,
        )
        actual = table_row_count(cursor, schema, table)

    print(f"Inserted rows: {inserted:,}")
    print(f"Table rows: {actual:,}")

    if inserted != expected or actual != expected:
        raise RuntimeError(
            f"Raw load row count mismatch. expected={expected:,}, "
            f"inserted={inserted:,}, table={actual:,}"
        )

    print("Raw load completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
