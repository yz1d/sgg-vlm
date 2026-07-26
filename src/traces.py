from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol, Sequence


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
class InlineTraceContent:
    """Trace content already held in memory."""

    data: bytes


@dataclass(frozen=True, slots=True)
class FileTraceContent:
    """Trace content to copy from an existing file."""

    source: Path


type TraceContent = InlineTraceContent | FileTraceContent


@dataclass(frozen=True, slots=True)
class Trace:
    """One stage-local inspection or audit output.

    ``path`` is relative to the stage's numbered output directory. The pipeline
    owns that directory and the trace store materializes the content beneath it.
    """

    path: PurePosixPath
    media_type: str
    content: TraceContent

    def __post_init__(self) -> None:
        if (
            self.path.is_absolute()
            or not self.path.parts
            or any(part in {"", ".", ".."} for part in self.path.parts)
        ):
            raise ValueError(f"Trace path must be a safe relative path: {self.path}")
        if not self.media_type:
            raise ValueError("Trace media type cannot be empty")

    @classmethod
    def json(cls, path: str, value: JsonValue) -> Trace:
        data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
        return cls(
            PurePosixPath(path),
            "application/json",
            InlineTraceContent(data),
        )

    @classmethod
    def text(cls, path: str, value: str) -> Trace:
        return cls(
            PurePosixPath(path),
            "text/plain; charset=utf-8",
            InlineTraceContent(value.encode("utf-8")),
        )

    @classmethod
    def bytes(cls, path: str, value: bytes, *, media_type: str) -> Trace:
        return cls(PurePosixPath(path), media_type, InlineTraceContent(value))

    @classmethod
    def file(cls, path: str, source: Path, *, media_type: str) -> Trace:
        return cls(PurePosixPath(path), media_type, FileTraceContent(Path(source)))


class TraceStore(Protocol):
    """Publishes traces without interpreting their contents."""

    def publish(self, directory: Path, traces: Sequence[Trace]) -> None: ...


class FileTraceStore:
    """Materialize inline and file-backed traces on the local filesystem."""

    def publish(self, directory: Path, traces: Sequence[Trace]) -> None:
        paths = [trace.path for trace in traces]
        if len(paths) != len(set(paths)):
            raise ValueError("Trace paths must be unique within a stage")
        for trace in traces:
            destination = directory.joinpath(*trace.path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(trace.content, InlineTraceContent):
                destination.write_bytes(trace.content.data)
            else:
                if not trace.content.source.is_file():
                    raise FileNotFoundError(
                        f"Trace source file does not exist: {trace.content.source}"
                    )
                shutil.copy2(trace.content.source, destination)
