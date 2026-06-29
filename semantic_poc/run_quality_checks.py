from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "semantic_poc" / "output"
PYTEST_BASETEMP = REPO_ROOT / ".tmp" / "pytest"
OUTPUT_FILENAMES = [
    "dbt_semantics.json",
    "powerbi_semantics.json",
    "proposed_powerbi_patch.json",
    "snowflake_semantic_view.yml",
    "semantic_compatibility.md",
]


def run_step(label: str, command: list[str]) -> None:
    print(f"\n== {label} ==")
    try:
        completed = subprocess.run(command, cwd=REPO_ROOT)
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing executable for {label}: {command[0]}") from exc
    if completed.returncode != 0:
        raise SystemExit(f"{label} failed with exit code {completed.returncode}")


def read_outputs() -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for filename in OUTPUT_FILENAMES:
        path = OUTPUT_DIR / filename
        if not path.is_file():
            raise SystemExit(f"Determinism check failed: missing output {path}")
        snapshot[filename] = path.read_bytes()
    return snapshot


def run_determinism_check() -> None:
    first = read_outputs()
    run_step("POC generation determinism pass", [sys.executable, "semantic_poc/run_poc.py", "--skip-dbt-parse"])
    second = read_outputs()
    changed = [filename for filename in OUTPUT_FILENAMES if first[filename] != second[filename]]
    if changed:
        raise SystemExit("Determinism check failed for: " + ", ".join(changed))
    print("Determinism check passed.")


def main() -> int:
    run_step("dbt parse", ["dbt", "--no-version-check", "parse"])
    PYTEST_BASETEMP.parent.mkdir(parents=True, exist_ok=True)
    run_step(
        "pytest",
        [
            sys.executable,
            "-m",
            "pytest",
            "semantic_poc/tests",
            "-q",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            str(PYTEST_BASETEMP),
        ],
    )
    run_step("POC generation", [sys.executable, "semantic_poc/run_poc.py", "--skip-dbt-parse"])
    run_determinism_check()
    print("\nQuality checks completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
