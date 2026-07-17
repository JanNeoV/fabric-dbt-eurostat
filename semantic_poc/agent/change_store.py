from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from semantic_poc.src.models import PROJECT_ROOT

from .schemas import MetricChangeRequest, validate_change_id


DEFAULT_CHANGE_DIR = PROJECT_ROOT / "semantic_poc" / "changes"


class ChangeStoreError(RuntimeError):
    """Base error for local change request persistence."""


class ChangeAlreadyExistsError(ChangeStoreError):
    pass


class ChangeNotFoundError(ChangeStoreError):
    pass


class ChangeStore:
    def __init__(self, root: Path = DEFAULT_CHANGE_DIR) -> None:
        self.root = root.resolve()

    def path_for(self, change_id: str) -> Path:
        validate_change_id(change_id)
        return self.root / f"{change_id}.json"

    def save(self, request: MetricChangeRequest) -> Path:
        validated = MetricChangeRequest.from_dict(request.to_dict())
        path = self.path_for(validated.change_id)
        self.root.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.root,
                prefix=".change-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(validated.to_dict(), handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_path, path)
            except FileExistsError as exc:
                raise ChangeAlreadyExistsError(
                    f"Change request already exists: {validated.change_id}"
                ) from exc
            except OSError as exc:
                raise ChangeStoreError(
                    f"Change request could not be published atomically: {validated.change_id}: {exc}"
                ) from exc
            return path
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def load(self, change_id: str) -> MetricChangeRequest:
        path = self.path_for(change_id)
        if not path.is_file():
            raise ChangeNotFoundError(f"Change request does not exist: {change_id}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return MetricChangeRequest.from_dict(data)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ChangeStoreError(f"Invalid stored change request {change_id}: {exc}") from exc

    def list(self) -> tuple[MetricChangeRequest, ...]:
        if not self.root.is_dir():
            return ()
        requests = []
        for path in sorted(self.root.glob("chg_*.json")):
            requests.append(self.load(path.stem))
        return tuple(requests)
