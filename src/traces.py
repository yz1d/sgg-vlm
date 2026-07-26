from __future__ import annotations

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

    @classmethod
    def json(cls, path: str, value: JsonValue) -> Trace:
        raise NotImplementedError

    @classmethod
    def text(cls, path: str, value: str) -> Trace:
        raise NotImplementedError

    @classmethod
    def bytes(cls, path: str, value: bytes, *, media_type: str) -> Trace:
        raise NotImplementedError

    @classmethod
    def file(cls, path: str, source: Path, *, media_type: str) -> Trace:
        raise NotImplementedError


class TraceStore(Protocol):
    """Publishes traces without interpreting their contents."""

    def publish(self, directory: Path, traces: Sequence[Trace]) -> None: ...
