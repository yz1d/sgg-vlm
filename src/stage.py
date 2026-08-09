from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.frame import Frame
from src.graph._generated.models import (
    Relation,
    Scene,
    SceneObject,
    WeatherCondition,
)
from src.traces import Trace


@dataclass(frozen=True, slots=True)
class StageOutput:
    """Graph upserts and non-semantic traces produced by one stage."""

    objects: tuple[SceneObject, ...] = ()
    relations: tuple[Relation, ...] = ()
    weather: WeatherCondition | None = None
    traces: tuple[Trace, ...] = ()


def apply_stage_output(graph: Scene, output: StageOutput) -> Scene:
    """Create a scene that contains the current records and stage output."""

    objects = list(graph.objects)
    object_index = {object_.id: index for index, object_ in enumerate(objects)}
    output_ids: set[str] = set()
    for object_ in output.objects:
        if object_.id in output_ids:
            raise ValueError(f"Stage output contains duplicate object ID {object_.id}")
        output_ids.add(object_.id)
        index = object_index.get(object_.id)
        if index is None:
            object_index[object_.id] = len(objects)
            objects.append(object_)
            continue
        current = objects[index]
        if current.type != object_.type:
            raise ValueError(
                f"Stage output cannot change object {object_.id} from "
                f"{current.type} to {object_.type}"
            )
        objects[index] = object_

    payload = graph.model_dump(mode="python")
    payload.update(
        objects=objects,
        relations=[*graph.relations, *output.relations],
    )
    if output.weather is not None:
        payload["weather"] = output.weather
    return Scene.model_validate(payload)


class Stage(Protocol):
    """A source-independent graph enrichment step."""

    name: str

    def run(self, frame: Frame) -> StageOutput: ...
