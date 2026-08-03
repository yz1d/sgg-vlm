from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Sequence


type JsonValue = (
    None
    | bool
    | int
    | float
    | str
    | list[JsonValue]
    | dict[str, JsonValue]
)


@dataclass(frozen=True, slots=True)
class Trace:
    """One stage-local inspection or audit output."""

    path: PurePosixPath
    data: bytes

    def __post_init__(self) -> None:
        if (
            self.path.is_absolute()
            or not self.path.parts
            or any(part in {"", ".", ".."} for part in self.path.parts)
        ):
            raise ValueError(f"Trace path must be a safe relative path: {self.path}")

    @classmethod
    def json(cls, path: str, value: JsonValue) -> Trace:
        data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
        return cls(PurePosixPath(path), data)

    @classmethod
    def text(cls, path: str, value: str) -> Trace:
        return cls(PurePosixPath(path), value.encode("utf-8"))

    @classmethod
    def bytes(cls, path: str, value: bytes) -> Trace:
        return cls(PurePosixPath(path), value)


def publish_traces(directory: Path, traces: Sequence[Trace]) -> None:
    """Write traces without overwriting another stage artifact."""

    paths = [trace.path for trace in traces]
    if len(paths) != len(set(paths)):
        raise ValueError("Trace paths must be unique within a stage")
    for trace in traces:
        destination = directory.joinpath(*trace.path.parts)
        if destination.exists():
            raise FileExistsError(f"Trace output already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(trace.data)
