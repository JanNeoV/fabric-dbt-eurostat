from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from semantic_poc.src.models import REQUIRED_PUBLIC_METRICS
from semantic_poc.src.snowflake_semantic_view import (
    VERIFY_SQL,
    read_semantic_view_yaml,
    run_snowflake_semantic_view_command,
    target_schema_name,
)


ENVIRONMENT = {
    "database": "TRIATHLON",
    "mart_schema": "MART",
    "semantic_schema": "SEMANTIC",
    "semantic_view_name": "TRIATHLON_ANALYTICS",
    "warehouse": "COMPUTE_WH",
    "role": "SEMANTIC_POC_ROLE",
}


SEMANTIC_VIEW_YAML = {
    "name": "TRIATHLON_ANALYTICS",
    "description": "Test semantic view.",
    "tables": [
        {
            "name": "results",
            "base_table": {"database": "TRIATHLON", "schema": "MART", "table": "FCT_RESULT"},
            "dimensions": [{"name": "result_id", "expr": "result_id", "data_type": "VARCHAR"}],
            "facts": [
                {"name": "is_valid_sbr_finisher", "expr": "is_valid_sbr_finisher", "data_type": "BOOLEAN"},
                {"name": "event_context_flag", "expr": "event_context_flag", "data_type": "BOOLEAN"},
            ],
            "metrics": [
                {"name": "valid_sbr_finishers", "expr": "COUNT_IF(is_valid_sbr_finisher)"},
                {"name": "event_context_rows", "expr": "COUNT_IF(event_context_flag)"},
            ],
        },
        {
            "name": "events",
            "base_table": {"database": "TRIATHLON", "schema": "MART", "table": "DIM_EVENT"},
            "dimensions": [{"name": "event_id", "expr": "event_id", "data_type": "VARCHAR"}],
        },
    ],
    "relationships": [
        {
            "name": "results_to_events",
            "left_table": "results",
            "right_table": "events",
            "relationship_columns": [{"left_column": "event_id", "right_column": "event_id"}],
        }
    ],
    "metrics": [
        {
            "name": "event_context_rate",
            "expr": "results.event_context_rows / NULLIF(results.valid_sbr_finishers, 0)",
        }
    ],
}


class FakeCursor:
    def __init__(self, *, fail_on: str | None = None, fail_message: str = "boom") -> None:
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []
        self.description: list[tuple[str]] = []
        self.rows: list[tuple[Any, ...]] = []
        self.fail_on = fail_on
        self.fail_message = fail_message

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> "FakeCursor":
        self.calls.append((sql, params))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError(self.fail_message)
        if sql == VERIFY_SQL:
            self.description = [("SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML",)]
            self.rows = [("YAML valid" if params and params[2] is True else "Semantic view created",)]
        elif sql.startswith("DESCRIBE SEMANTIC VIEW"):
            self.description = [("object_kind",), ("object_name",)]
            self.rows = [("SEMANTIC_VIEW", "TRIATHLON_ANALYTICS")]
        elif sql.startswith("SHOW SEMANTIC METRICS"):
            self.description = [("name",)]
            self.rows = [(metric,) for metric in REQUIRED_PUBLIC_METRICS]
        elif sql.startswith("SELECT * FROM SEMANTIC_VIEW"):
            self.description = [("value",)]
            self.rows = [(1,)]
        else:
            self.description = []
            self.rows = []
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        if not self.rows:
            return None
        return self.rows.pop(0)

    def fetchall(self) -> list[tuple[Any, ...]]:
        rows = self.rows
        self.rows = []
        return rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self._cursor


class FakeConnector:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor = cursor
        self.kwargs: dict[str, Any] | None = None

    def __call__(self, **kwargs: Any) -> FakeConnection:
        self.kwargs = kwargs
        return FakeConnection(self.cursor)


def write_inputs(tmp_path: Path, yaml_data: dict[str, Any] | None = None) -> tuple[Path, Path, Path]:
    yaml_path = tmp_path / "snowflake_semantic_view.yml"
    environment_path = tmp_path / "snowflake_environment.yml"
    output_dir = tmp_path / "output"
    yaml_path.write_text(yaml.safe_dump(yaml_data or SEMANTIC_VIEW_YAML, sort_keys=False), encoding="utf-8", newline="\n")
    environment_path.write_text(yaml.safe_dump(ENVIRONMENT, sort_keys=False), encoding="utf-8", newline="\n")
    return yaml_path, environment_path, output_dir


def procedure_calls(cursor: FakeCursor) -> list[tuple[str, tuple[Any, ...] | None]]:
    return [call for call in cursor.calls if call[0] == VERIFY_SQL]


def test_verification_only_mode_calls_verify_only(tmp_path: Path) -> None:
    yaml_path, environment_path, output_dir = write_inputs(tmp_path)
    cursor = FakeCursor()
    connector = FakeConnector(cursor)

    outcome = run_snowflake_semantic_view_command(
        action="verify",
        yaml_path=yaml_path,
        environment_path=environment_path,
        output_dir=output_dir,
        connector=connector,
        stream=io.StringIO(),
    )

    calls = procedure_calls(cursor)
    assert outcome.return_code == 0
    assert len(calls) == 1
    assert calls[0][1][0] == "TRIATHLON.SEMANTIC"
    assert calls[0][1][2] is True
    assert outcome.report["deployment_performed"] is False


def test_deployment_is_blocked_without_apply(tmp_path: Path) -> None:
    yaml_path, environment_path, output_dir = write_inputs(tmp_path)
    cursor = FakeCursor()

    outcome = run_snowflake_semantic_view_command(
        action="deploy",
        yaml_path=yaml_path,
        environment_path=environment_path,
        output_dir=output_dir,
        connector=FakeConnector(cursor),
        stream=io.StringIO(),
    )

    calls = procedure_calls(cursor)
    assert outcome.return_code == 0
    assert len(calls) == 1
    assert calls[0][1][2] is True
    assert outcome.report["deployment_status"] == "blocked_without_apply"
    assert outcome.report["deployment_performed"] is False


def test_unresolved_placeholders_are_rejected_before_connecting(tmp_path: Path) -> None:
    yaml_path, environment_path, output_dir = write_inputs(tmp_path)
    yaml_path.write_text("name: <VIEW_NAME>\ntables: []\nrelationships: []\nmetrics: []\n", encoding="utf-8")
    called = False

    def connector(**_kwargs: Any) -> FakeConnection:
        nonlocal called
        called = True
        return FakeConnection(FakeCursor())

    outcome = run_snowflake_semantic_view_command(
        action="verify",
        yaml_path=yaml_path,
        environment_path=environment_path,
        output_dir=output_dir,
        connector=connector,
        stream=io.StringIO(),
    )

    assert outcome.return_code == 1
    assert called is False
    assert "unresolved placeholders" in " ".join(outcome.report["errors"])


def test_yaml_file_reading(tmp_path: Path) -> None:
    yaml_path, _environment_path, _output_dir = write_inputs(tmp_path)

    loaded = read_semantic_view_yaml(yaml_path)

    assert "TRIATHLON_ANALYTICS" in loaded.text
    assert loaded.data["name"] == "TRIATHLON_ANALYTICS"


def test_target_schema_construction_supports_old_and_new_config_keys() -> None:
    assert target_schema_name(ENVIRONMENT) == "TRIATHLON.SEMANTIC"
    assert (
        target_schema_name(
            {
                "database": "TRIATHLON",
                "schema": "MART",
                "semantic_view_schema": "SEMANTIC",
                "semantic_view_name": "TRIATHLON_ANALYTICS",
            }
        )
        == "TRIATHLON.SEMANTIC"
    )


def test_secret_free_error_reporting_and_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path, environment_path, output_dir = write_inputs(tmp_path)
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "supersecret")
    stream = io.StringIO()
    cursor = FakeCursor(fail_on="SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML", fail_message="bad password supersecret")

    outcome = run_snowflake_semantic_view_command(
        action="verify",
        yaml_path=yaml_path,
        environment_path=environment_path,
        output_dir=output_dir,
        connector=FakeConnector(cursor),
        stream=stream,
    )

    assert outcome.return_code == 1
    rendered = stream.getvalue() + json.dumps(outcome.report)
    assert "supersecret" not in rendered
    assert "[REDACTED]" in json.dumps(outcome.report)


def test_snowflake_exception_reporting(tmp_path: Path) -> None:
    yaml_path, environment_path, output_dir = write_inputs(tmp_path)
    cursor = FakeCursor(fail_on="SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML", fail_message="Snowflake exploded")

    outcome = run_snowflake_semantic_view_command(
        action="verify",
        yaml_path=yaml_path,
        environment_path=environment_path,
        output_dir=output_dir,
        connector=FakeConnector(cursor),
        stream=io.StringIO(),
    )

    assert outcome.return_code == 1
    assert outcome.report["verification_status"] == "failed"
    assert outcome.report["errors"] == ["Snowflake exploded"]


def test_successful_verification_response_is_saved(tmp_path: Path) -> None:
    yaml_path, environment_path, output_dir = write_inputs(tmp_path)

    outcome = run_snowflake_semantic_view_command(
        action="verify",
        yaml_path=yaml_path,
        environment_path=environment_path,
        output_dir=output_dir,
        connector=FakeConnector(FakeCursor()),
        stream=io.StringIO(),
    )

    report = json.loads(outcome.json_path.read_text(encoding="utf-8"))
    assert outcome.return_code == 0
    assert report["snowflake_response"] == "YAML valid"
    assert report["verification_status"] == "succeeded"


def test_successful_deployment_response_and_smoke_results(tmp_path: Path) -> None:
    yaml_path, environment_path, output_dir = write_inputs(tmp_path)
    cursor = FakeCursor()

    outcome = run_snowflake_semantic_view_command(
        action="deploy",
        yaml_path=yaml_path,
        environment_path=environment_path,
        output_dir=output_dir,
        apply=True,
        connector=FakeConnector(cursor),
        stream=io.StringIO(),
    )

    calls = procedure_calls(cursor)
    assert outcome.return_code == 0
    assert [call[1][2] for call in calls] == [True, False]
    assert outcome.report["deployment_performed"] is True
    assert outcome.report["deployment_response"] == "Semantic view created"
    assert outcome.report["smoke_tests"]["success"] is True
    assert {query["name"] for query in outcome.report["smoke_tests"]["queries"]} == {
        "valid_sbr_finishers",
        "event_context_rate",
    }


@pytest.mark.skipif(os.getenv("RUN_SNOWFLAKE_INTEGRATION_TESTS") != "1", reason="Snowflake integration tests are opt-in.")
def test_live_snowflake_verification_opt_in() -> None:
    outcome = run_snowflake_semantic_view_command(action="verify")
    assert outcome.return_code == 0
