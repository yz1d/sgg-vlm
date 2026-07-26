from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.frame import Frame
from src.graph.changes import SceneChange
from src.traces import Trace


@dataclass(frozen=True, slots=True)
class StageOutput:
    """Semantic changes and non-semantic traces produced by one stage."""

    changes: tuple[SceneChange, ...] = ()
    traces: tuple[Trace, ...] = ()


class Stage(Protocol):
    """A source-independent graph enrichment step."""

    name: str
    allowed_changes: tuple[type, ...]

    def run(self, frame: Frame) -> StageOutput: ...
