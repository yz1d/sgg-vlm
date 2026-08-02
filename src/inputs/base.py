from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.frame import Frame
from src.graph._generated.models import EgoVehicle, Provenance, Scene
from src.traces import Trace


@dataclass(frozen=True, slots=True)
class InputContext:
    """Pipeline-owned scratch space for materializing an input frame."""

    workspace: Path


@dataclass(frozen=True, slots=True)
class SourceFrame:
    """One frame loaded from an input source and its source traces."""

    frame: Frame
    traces: tuple[Trace, ...] = ()


class InputSource(Protocol):
    name: str

    def load(self, context: InputContext) -> SourceFrame: ...


def empty_scene(*, source: str, timestamp_ns: int | None) -> Scene:
    """Create the valid empty graph shared by raw-image input sources."""

    provenance = Provenance(source=source, stage="input")
    return Scene(
        frame_id="frame_000001",
        timestamp_ns=timestamp_ns,
        provenance=[provenance],
        ego=EgoVehicle(id="ego", provenance=[provenance]),
        road_users=[],
        road_regions=[],
        states=[],
        relationships=[],
    )
