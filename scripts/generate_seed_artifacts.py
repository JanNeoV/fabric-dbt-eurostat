from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "data" / "raw" / "coachcox_results"
DEFAULT_SEED_DIR = ROOT / "seeds"
RAW_SEED_NAME = "coachcox_results_raw.csv"
MANIFEST_SEED_NAME = "coachcox_seed_manifest.csv"

RAW_COLUMN_MAP = {
    "Bib": "bib",
    "Name": "name",
    "Country": "country",
    "Gender": "gender",
    "Division": "division",
    "Overall Time": "overall_time",
    "Overall Rank": "overall_rank",
    "Gender Rank": "gender_rank",
    "Age Group Rank": "age_group_rank",
    "Swim Time": "swim_time",
    "Swim Rank": "swim_rank",
    "Gender Swim Rank": "gender_swim_rank",
    "Age Group Swim Rank": "age_group_swim_rank",
    "Bike Time": "bike_time",
    "Bike Rank": "bike_rank",
    "Gender Bike Rank": "gender_bike_rank",
    "Age Group Bike Rank": "age_group_bike_rank",
    "Run Time": "run_time",
    "Run Rank": "run_rank",
    "Gender Run Rank": "gender_run_rank",
    "Age Group Run Rank": "age_group_run_rank",
    "Transition 1 Time": "transition_1_time",
    "Transition 1 Rank": "transition_1_rank",
    "Gender Transition 1 Rank": "gender_transition_1_rank",
    "Age Group Transition 1 Rank": "age_group_transition_1_rank",
    "Transition 2 Time": "transition_2_time",
    "Transition 2 Rank": "transition_2_rank",
    "Gender Transition 2 Rank": "gender_transition_2_rank",
    "Age Group Transition 2 Rank": "age_group_transition_2_rank",
    "Finish": "finish",
    "Qualifier Time": "qualifier_time",
    "Qualifier Rank": "qualifier_rank",
    "Gender Qualifier Rank": "gender_qualifier_rank",
    "Qualified": "qualified",
}

METADATA_COLUMNS = [
    "source_seed_name",
    "source_file_name",
    "source_row_number",
    "event_id",
    "race_slug",
    "race_name",
    "year",
    "distance",
]
RAW_OUTPUT_COLUMNS = list(RAW_COLUMN_MAP.values())
RAW_SEED_COLUMNS = METADATA_COLUMNS + RAW_OUTPUT_COLUMNS
MANIFEST_COLUMNS = [
    "source_seed_name",
    "source_file_name",
    "event_id",
    "race_slug",
    "race_name",
    "year",
    "distance",
    "source_row_count",
]

EXCLUDED_INPUT_FILES = {RAW_SEED_NAME, MANIFEST_SEED_NAME}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build compact CoachCox dbt seed artifacts from raw result CSV files."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing individual CoachCox CSV files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--seed-dir",
        type=Path,
        default=DEFAULT_SEED_DIR,
        help=f"Directory where generated dbt seed CSVs are written. Default: {DEFAULT_SEED_DIR}",
    )
    return parser.parse_args()


def source_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(
            f"No input directory found at {input_dir}. "
            "Move raw CoachCox CSV files into data/raw/coachcox_results first."
        )

    files = sorted(
        path
        for path in input_dir.glob("*.csv")
        if path.name not in EXCLUDED_INPUT_FILES
    )
    if not files:
        raise FileNotFoundError(f"No CoachCox CSV files found in {input_dir}.")
    return files


def normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def parse_seed_name(seed_name: str) -> dict[str, str | int | None]:
    match = re.match(r"^(?P<slug>.*?)(?P<year>\d{4})(?:-results)?__(?P<event_id>\d+)$", seed_name)
    if match:
        slug = match.group("slug")
        year = int(match.group("year"))
        event_id = match.group("event_id")
    else:
        slug = seed_name
        year = None
        event_id = seed_name

    if seed_name.startswith("ironman70.3"):
        distance = "70.3"
    elif seed_name.startswith("ironman"):
        distance = "full"
    else:
        distance = "unknown"

    return {
        "event_id": event_id,
        "race_slug": slug,
        "race_name": humanize_race_name(slug),
        "year": year,
        "distance": distance,
    }


def humanize_race_name(slug: str) -> str:
    if slug.startswith("ironman70.3"):
        prefix = "Ironman 70.3 "
        rest = slug[len("ironman70.3") :]
    elif slug.startswith("ironman"):
        prefix = "Ironman "
        rest = slug[len("ironman") :]
    elif slug.startswith("challenge"):
        prefix = "Challenge "
        rest = slug[len("challenge") :]
    else:
        prefix = ""
        rest = slug

    rest = rest.replace("-", " ").replace("_", " ").strip()
    if not rest:
        return prefix.strip()
    return prefix + " ".join(part.capitalize() for part in rest.split())


def validate_header(path: Path, fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise ValueError(f"{path.name} has no CSV header.")

    actual_by_normalized: dict[str, str] = {}
    duplicates: list[str] = []
    for fieldname in fieldnames:
        normalized = normalize_header(fieldname)
        if normalized in actual_by_normalized:
            duplicates.append(fieldname)
        actual_by_normalized[normalized] = fieldname

    expected = {normalize_header(column): column for column in RAW_COLUMN_MAP}
    missing = [expected[key] for key in expected if key not in actual_by_normalized]
    extra = [actual_by_normalized[key] for key in actual_by_normalized if key not in expected]

    if missing or extra or duplicates:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        if duplicates:
            details.append(f"duplicates={duplicates}")
        raise ValueError(f"{path.name} header mismatch: {'; '.join(details)}")

    return {
        output_column: actual_by_normalized[normalize_header(input_column)]
        for input_column, output_column in RAW_COLUMN_MAP.items()
    }


def build_artifacts(input_dir: Path, seed_dir: Path) -> tuple[int, int]:
    files = source_files(input_dir)
    seed_dir.mkdir(parents=True, exist_ok=True)

    raw_seed_path = seed_dir / RAW_SEED_NAME
    manifest_seed_path = seed_dir / MANIFEST_SEED_NAME
    manifest_rows: list[dict[str, object]] = []
    total_rows = 0

    with raw_seed_path.open("w", newline="", encoding="utf-8") as raw_handle:
        raw_writer = csv.DictWriter(raw_handle, fieldnames=RAW_SEED_COLUMNS)
        raw_writer.writeheader()

        for path in files:
            metadata = parse_seed_name(path.stem)
            source_seed_name = path.stem
            row_count = 0

            with path.open("r", newline="", encoding="utf-8-sig") as input_handle:
                reader = csv.DictReader(input_handle)
                column_lookup = validate_header(path, reader.fieldnames)

                for source_row_number, row in enumerate(reader, start=1):
                    if None in row:
                        raise ValueError(
                            f"{path.name} row {source_row_number} has more fields than the header."
                        )

                    output_row = {
                        "source_seed_name": source_seed_name,
                        "source_file_name": path.name,
                        "source_row_number": source_row_number,
                        **metadata,
                    }
                    for output_column in RAW_OUTPUT_COLUMNS:
                        value = row.get(column_lookup[output_column], "")
                        output_row[output_column] = "" if value is None else value

                    raw_writer.writerow(output_row)
                    row_count += 1

            manifest_rows.append(
                {
                    "source_seed_name": source_seed_name,
                    "source_file_name": path.name,
                    **metadata,
                    "source_row_count": row_count,
                }
            )
            total_rows += row_count

    with manifest_seed_path.open("w", newline="", encoding="utf-8") as manifest_handle:
        manifest_writer = csv.DictWriter(manifest_handle, fieldnames=MANIFEST_COLUMNS)
        manifest_writer.writeheader()
        manifest_writer.writerows(manifest_rows)

    return len(files), total_rows


def main() -> None:
    args = parse_args()
    file_count, row_count = build_artifacts(args.input_dir, args.seed_dir)
    print(
        f"Generated {RAW_SEED_NAME} and {MANIFEST_SEED_NAME} "
        f"from {file_count:,} files and {row_count:,} rows."
    )


if __name__ == "__main__":
    main()
