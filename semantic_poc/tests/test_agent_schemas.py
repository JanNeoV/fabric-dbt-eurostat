from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from semantic_poc.agent.approvals import InvalidStateTransition, allowed_transitions, validate_transition
from semantic_poc.agent.change_store import ChangeAlreadyExistsError, ChangeStore
from semantic_poc.agent.schemas import (
    ApprovalState,
    ChangeIntent,
    ChangeMode,
    ChangeStatus,
    DeploymentState,
    MetricChangeRequest,
    TargetName,
    TargetSupport,
    ValidationState,
)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "agent" / "metric_change_request.schema.json"


def example_request() -> MetricChangeRequest:
    return MetricChangeRequest.create(
        user_request="Update valid_sbr_finishers.",
        intent=ChangeIntent.UPDATE_METRIC,
        canonical_metric_name="valid_sbr_finishers",
        requested_semantic_change="Exclude specified finish statuses.",
        affected_targets=(TargetName.CANONICAL_DBT, TargetName.POWER_BI, TargetName.SNOWFLAKE),
        target_support={
            TargetName.CANONICAL_DBT: TargetSupport.SUPPORTED_PATTERN,
            TargetName.POWER_BI: TargetSupport.SUPPORTED_PATTERN,
            TargetName.SNOWFLAKE: TargetSupport.SUPPORTED_PATTERN,
        },
        now=datetime(2026, 7, 17, 12, 30, 45, tzinfo=timezone.utc),
        entropy="a1b2c3d4",
        assumptions=("No deployment is requested.",),
    )


def test_change_request_defaults_and_round_trip() -> None:
    request = example_request()

    assert request.change_id == "chg_20260717T123045Z_a1b2c3d4"
    assert request.created_at == "2026-07-17T12:30:45Z"
    assert request.mode == ChangeMode.PROPOSE
    assert request.status == ChangeStatus.DRAFT
    assert request.approval_state == ApprovalState.REQUIRED
    assert request.validation_state == ValidationState.NOT_RUN
    assert request.deployment_state == DeploymentState.NOT_REQUESTED
    assert MetricChangeRequest.from_dict(request.to_dict()) == request

    with pytest.raises(TypeError):
        request.target_support[TargetName.POWER_BI] = TargetSupport.UNSUPPORTED  # type: ignore[index]


def test_change_request_rejects_unknown_fields_and_mismatched_targets() -> None:
    data = example_request().to_dict()
    data["secret"] = "must-not-be-accepted"
    with pytest.raises(ValueError, match="unexpected: secret"):
        MetricChangeRequest.from_dict(data)

    data = example_request().to_dict()
    del data["target_support"]["SNOWFLAKE"]
    with pytest.raises(ValueError, match="exactly match"):
        MetricChangeRequest.from_dict(data)


def test_json_schema_matches_serialized_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = example_request().to_dict()

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(payload)
    assert schema["properties"]["canonical_file"]["const"] == "models/semantic/triathlon_semantic.yml"
    assert set(schema["properties"]["intent"]["enum"]) == {item.value for item in ChangeIntent}


def test_change_store_is_atomic_non_overwriting_and_path_safe(tmp_path: Path) -> None:
    store = ChangeStore(tmp_path / "changes")
    request = example_request()

    path = store.save(request)
    assert path.name == f"{request.change_id}.json"
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert store.load(request.change_id) == request
    assert store.list() == (request,)
    assert list(path.parent.glob(".change-*.tmp")) == []

    with pytest.raises(ChangeAlreadyExistsError):
        store.save(request)
    with pytest.raises(ValueError, match="Invalid change ID"):
        store.path_for("../../escape")


def test_change_store_does_not_overwrite_a_competing_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ChangeStore(tmp_path / "changes")
    request = example_request()
    destination = store.path_for(request.change_id)
    original_link = os.link

    def publish_competing_file(source: str | Path, target: str | Path) -> None:
        Path(target).write_text("competing writer\n", encoding="utf-8")
        original_link(source, target)

    monkeypatch.setattr("semantic_poc.agent.change_store.os.link", publish_competing_file)

    with pytest.raises(ChangeAlreadyExistsError):
        store.save(request)

    assert destination.read_text(encoding="utf-8") == "competing writer\n"
    assert list(destination.parent.glob(".change-*.tmp")) == []


def test_lifecycle_transitions_are_explicit() -> None:
    assert ChangeStatus.PROPOSED in allowed_transitions(ChangeStatus.DRAFT)
    validate_transition(ChangeStatus.PROPOSED, ChangeStatus.APPROVED)

    with pytest.raises(InvalidStateTransition, match="DRAFT to APPLIED_LOCAL"):
        validate_transition(ChangeStatus.DRAFT, ChangeStatus.APPLIED_LOCAL)
    with pytest.raises(InvalidStateTransition, match="VALIDATED to"):
        validate_transition(ChangeStatus.VALIDATED, ChangeStatus.PROPOSED)
