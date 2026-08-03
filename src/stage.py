from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.frame import Frame
from src.graph._generated.models import (
    ObjectState,
    PerceivedRoadUser,
    Relationship,
    RoadRegion,
    Scene,
)
from src.traces import Trace


@dataclass(frozen=True, slots=True)
class StageOutput:
    """Graph additions and non-semantic traces produced by one stage."""

    road_users: tuple[PerceivedRoadUser, ...] = ()
    road_regions: tuple[RoadRegion, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    states: tuple[ObjectState, ...] = ()
    traces: tuple[Trace, ...] = ()


def apply_stage_output(graph: Scene, output: StageOutput) -> Scene:
    """Create a scene that contains the current records and stage additions."""

    payload = graph.model_dump(mode="python")
    payload.update(
        road_users=[*(graph.road_users or []), *output.road_users],
        road_regions=[*(graph.road_regions or []), *output.road_regions],
        relationships=[*(graph.relationships or []), *output.relationships],
        states=[*(graph.states or []), *output.states],
    )
    return Scene.model_validate(payload)


class Stage(Protocol):
    """A source-independent graph enrichment step."""

    name: str

    def run(self, frame: Frame) -> StageOutput: ...
