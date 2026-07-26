from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.graph.models import PerceivedRoadUser

PROMPT_ANNOTATION = "object_detection_prompt"


type RoadUserModel = type[PerceivedRoadUser]


@dataclass(frozen=True, slots=True)
class DetectionTarget:
    """A detectable graph type and its schema-owned prompt phrase."""

    prompt: str
    road_user_model: RoadUserModel


def detection_targets() -> tuple[DetectionTarget, ...]:
    """Discover detectable concrete road-user types from LinkML metadata."""

    targets: list[DetectionTarget] = []
    prompts: dict[str, RoadUserModel] = {}
    for model in _descendants(PerceivedRoadUser):
        metadata = model.linkml_meta.root
        if metadata.get("abstract") is True:
            continue
        prompt = _annotation_value(metadata, PROMPT_ANNOTATION)
        if prompt is None:
            continue
        normalized = prompt.casefold()
        previous = prompts.get(normalized)
        if previous is not None:
            raise ValueError(
                f"Detection prompt {prompt!r} belongs to both "
                f"{previous.__name__} and {model.__name__}"
            )
        prompts[normalized] = model
        targets.append(DetectionTarget(prompt, model))
    return tuple(sorted(targets, key=lambda target: target.prompt.casefold()))


def _descendants(model: RoadUserModel) -> tuple[RoadUserModel, ...]:
    descendants: list[RoadUserModel] = []
    for child in model.__subclasses__():
        descendants.append(child)
        descendants.extend(_descendants(child))
    return tuple(descendants)


def _annotation_value(metadata: dict[str, Any], name: str) -> str | None:
    annotation = (metadata.get("annotations") or {}).get(name)
    if annotation is None:
        return None
    value = annotation.get("value") if isinstance(annotation, dict) else annotation
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"LinkML annotation {name} must be a nonempty string")
    return value.strip()
