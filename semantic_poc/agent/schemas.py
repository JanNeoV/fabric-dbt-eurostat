from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


SCHEMA_VERSION = 1
CANONICAL_FILE = "models/semantic/triathlon_semantic.yml"
CHANGE_ID_PATTERN = re.compile(r"^chg_\d{8}T\d{6}Z_[0-9a-f]{8}$")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class ChangeIntent(str, Enum):
    CREATE_METRIC = "CREATE_METRIC"
    UPDATE_METRIC = "UPDATE_METRIC"
    RENAME_METRIC = "RENAME_METRIC"
    DEPRECATE_METRIC = "DEPRECATE_METRIC"
    RECONCILE_TARGET_DRIFT = "RECONCILE_TARGET_DRIFT"


class ChangeMode(str, Enum):
    PROPOSE = "PROPOSE"
    APPLY_LOCAL = "APPLY_LOCAL"
    VALIDATE = "VALIDATE"


class TargetSupport(str, Enum):
    SUPPORTED_PATTERN = "SUPPORTED_PATTERN"
    METADATA_ONLY = "METADATA_ONLY"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"


class TargetName(str, Enum):
    CANONICAL_DBT = "CANONICAL_DBT"
    POWER_BI = "POWER_BI"
    SNOWFLAKE = "SNOWFLAKE"


class ChangeStatus(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    APPLIED_LOCAL = "APPLIED_LOCAL"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ApprovalState(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    REQUIRED = "REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ValidationState(str, Enum):
    NOT_RUN = "NOT_RUN"
    PASSED = "PASSED"
    FAILED = "FAILED"


class DeploymentState(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    NOT_PERFORMED = "NOT_PERFORMED"
    BLOCKED = "BLOCKED"


def utc_timestamp(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp source must be timezone-aware.")
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_change_id(now: datetime | None = None, entropy: str | None = None) -> str:
    timestamp = utc_timestamp(now).replace("-", "").replace(":", "")
    suffix = entropy or uuid.uuid4().hex[:8]
    if not re.fullmatch(r"[0-9a-f]{8}", suffix):
        raise ValueError("Change ID entropy must contain exactly eight lowercase hexadecimal characters.")
    return f"chg_{timestamp}_{suffix}"


def validate_change_id(change_id: str) -> None:
    if not isinstance(change_id, str) or not CHANGE_ID_PATTERN.fullmatch(change_id):
        raise ValueError(f"Invalid change ID: {change_id!r}")


def validate_timestamp(value: str) -> None:
    if not isinstance(value, str) or not TIMESTAMP_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid UTC timestamp: {value!r}")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"Invalid UTC timestamp: {value!r}") from exc


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be an array of strings.")
    result = tuple(value)
    if any(not isinstance(item, str) for item in result):
        raise ValueError(f"{field_name} must be an array of strings.")
    return result


@dataclass(frozen=True)
class MetricChangeRequest:
    schema_version: int
    change_id: str
    created_at: str
    user_request: str
    intent: ChangeIntent
    mode: ChangeMode
    canonical_metric_name: str
    canonical_file: str
    requested_semantic_change: str
    affected_targets: tuple[TargetName, ...]
    target_support: Mapping[TargetName, TargetSupport]
    status: ChangeStatus
    approval_state: ApprovalState
    validation_state: ValidationState
    deployment_state: DeploymentState
    assumptions: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}.")
        validate_change_id(self.change_id)
        validate_timestamp(self.created_at)
        for field_name in (
            "user_request",
            "canonical_metric_name",
            "canonical_file",
            "requested_semantic_change",
        ):
            _required_text(getattr(self, field_name), field_name)
        if self.canonical_file != CANONICAL_FILE:
            raise ValueError(f"canonical_file must be {CANONICAL_FILE!r}.")
        if not self.affected_targets:
            raise ValueError("affected_targets must not be empty.")
        if len(set(self.affected_targets)) != len(self.affected_targets):
            raise ValueError("affected_targets must not contain duplicates.")
        normalized_support = dict(self.target_support)
        if set(normalized_support) != set(self.affected_targets):
            raise ValueError("target_support keys must exactly match affected_targets.")
        object.__setattr__(self, "target_support", MappingProxyType(normalized_support))
        object.__setattr__(self, "assumptions", _string_tuple(self.assumptions, "assumptions"))
        object.__setattr__(self, "diagnostics", _string_tuple(self.diagnostics, "diagnostics"))

    @classmethod
    def create(
        cls,
        *,
        user_request: str,
        intent: ChangeIntent,
        canonical_metric_name: str,
        requested_semantic_change: str,
        affected_targets: tuple[TargetName, ...],
        target_support: Mapping[TargetName, TargetSupport],
        now: datetime | None = None,
        entropy: str | None = None,
        assumptions: tuple[str, ...] = (),
        diagnostics: tuple[str, ...] = (),
    ) -> "MetricChangeRequest":
        return cls(
            schema_version=SCHEMA_VERSION,
            change_id=new_change_id(now, entropy),
            created_at=utc_timestamp(now),
            user_request=user_request,
            intent=intent,
            mode=ChangeMode.PROPOSE,
            canonical_metric_name=canonical_metric_name,
            canonical_file=CANONICAL_FILE,
            requested_semantic_change=requested_semantic_change,
            affected_targets=affected_targets,
            target_support=target_support,
            status=ChangeStatus.DRAFT,
            approval_state=ApprovalState.REQUIRED,
            validation_state=ValidationState.NOT_RUN,
            deployment_state=DeploymentState.NOT_REQUESTED,
            assumptions=assumptions,
            diagnostics=diagnostics,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "change_id": self.change_id,
            "created_at": self.created_at,
            "user_request": self.user_request,
            "intent": self.intent.value,
            "mode": self.mode.value,
            "canonical_metric_name": self.canonical_metric_name,
            "canonical_file": self.canonical_file,
            "requested_semantic_change": self.requested_semantic_change,
            "affected_targets": [target.value for target in self.affected_targets],
            "target_support": {
                target.value: self.target_support[target].value for target in self.affected_targets
            },
            "status": self.status.value,
            "approval_state": self.approval_state.value,
            "validation_state": self.validation_state.value,
            "deployment_state": self.deployment_state.value,
            "assumptions": list(self.assumptions),
            "diagnostics": list(self.diagnostics),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MetricChangeRequest":
        if not isinstance(data, Mapping):
            raise ValueError("Metric change request must be a JSON object.")
        expected = {
            "schema_version",
            "change_id",
            "created_at",
            "user_request",
            "intent",
            "mode",
            "canonical_metric_name",
            "canonical_file",
            "requested_semantic_change",
            "affected_targets",
            "target_support",
            "status",
            "approval_state",
            "validation_state",
            "deployment_state",
            "assumptions",
            "diagnostics",
        }
        missing = expected - set(data)
        extra = set(data) - expected
        if missing or extra:
            details = []
            if missing:
                details.append("missing: " + ", ".join(sorted(missing)))
            if extra:
                details.append("unexpected: " + ", ".join(sorted(extra)))
            raise ValueError("Invalid metric change request fields (" + "; ".join(details) + ").")
        try:
            targets = tuple(TargetName(item) for item in data["affected_targets"])
            raw_support = data["target_support"]
            if not isinstance(raw_support, Mapping):
                raise ValueError("target_support must be a JSON object.")
            support = {TargetName(key): TargetSupport(value) for key, value in raw_support.items()}
            return cls(
                schema_version=data["schema_version"],
                change_id=data["change_id"],
                created_at=data["created_at"],
                user_request=data["user_request"],
                intent=ChangeIntent(data["intent"]),
                mode=ChangeMode(data["mode"]),
                canonical_metric_name=data["canonical_metric_name"],
                canonical_file=data["canonical_file"],
                requested_semantic_change=data["requested_semantic_change"],
                affected_targets=targets,
                target_support=support,
                status=ChangeStatus(data["status"]),
                approval_state=ApprovalState(data["approval_state"]),
                validation_state=ValidationState(data["validation_state"]),
                deployment_state=DeploymentState(data["deployment_state"]),
                assumptions=_string_tuple(data["assumptions"], "assumptions"),
                diagnostics=_string_tuple(data["diagnostics"], "diagnostics"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and not isinstance(exc, KeyError):
                raise
            raise ValueError(f"Invalid metric change request: {exc}") from exc
