from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.graph.models import ObjectState, PerceivedRoadUser, SpatialRelationship
from src.graph.schema import schema_view

RELATION_EXTRACTION_ANNOTATION = "relation_extraction"
RELATION_EXTRACTION_PROMPT_ANNOTATION = "relation_extraction_prompt"
EXCLUSIVE_GROUP_ANNOTATION = "exclusive_group"


type RelationshipModel = type[SpatialRelationship]
type ObjectStateModel = type[ObjectState]
type RoadUserModel = type[PerceivedRoadUser]


@dataclass(frozen=True, slots=True)
class RelationshipTarget:
    model: RelationshipModel
    description: str
    exclusive_group: str | None


@dataclass(frozen=True, slots=True)
class StateValue:
    value: str
    description: str


@dataclass(frozen=True, slots=True)
class StateAttribute:
    name: str
    description: str
    values: tuple[StateValue, ...]


@dataclass(frozen=True, slots=True)
class StateTarget:
    model: ObjectStateModel
    description: str
    subject_model: RoadUserModel
    attributes: tuple[StateAttribute, ...]


def relationship_targets() -> tuple[RelationshipTarget, ...]:
    """Discover VLM-extractable relationships from generated LinkML metadata."""

    targets: list[RelationshipTarget] = []
    for model in _descendants(SpatialRelationship):
        metadata = model.linkml_meta.root
        if metadata.get("abstract") is True:
            continue
        if _annotation_value(metadata, RELATION_EXTRACTION_ANNOTATION) != "enabled":
            continue
        targets.append(
            RelationshipTarget(
                model=model,
                description=_description(model),
                exclusive_group=_annotation_value(
                    metadata, EXCLUSIVE_GROUP_ANNOTATION
                ),
            )
        )
    return tuple(sorted(targets, key=lambda target: target.model.__name__))


def state_targets() -> tuple[StateTarget, ...]:
    """Discover concrete object states and their schema-defined applicability."""

    road_user_models = {
        model.__name__: model
        for model in (PerceivedRoadUser, *_descendants(PerceivedRoadUser))
    }
    targets: list[StateTarget] = []
    system_fields = {"type", "subject", "confidence", "provenance"}
    for model in _descendants(ObjectState):
        metadata = model.linkml_meta.root
        if metadata.get("abstract") is True:
            continue
        subject_usage = (metadata.get("slot_usage") or {}).get("subject") or {}
        subject_range = subject_usage.get("range", "PerceivedRoadUser")
        subject_model = road_user_models.get(subject_range)
        if subject_model is None:
            raise ValueError(
                f"Object state {model.__name__} has unknown subject range "
                f"{subject_range!r}"
            )

        attributes: list[StateAttribute] = []
        for name, field in model.model_fields.items():
            if name in system_fields:
                continue
            annotation = field.annotation
            if not isinstance(annotation, type) or not issubclass(annotation, Enum):
                raise ValueError(
                    f"Object state field {model.__name__}.{name} must use an enum"
                )
            enum_definition = schema_view().get_enum(annotation.__name__)
            if enum_definition is None:
                raise ValueError(
                    f"Object state field {model.__name__}.{name} uses unknown "
                    f"enum {annotation.__name__}"
                )
            values: list[StateValue] = []
            for member in annotation:
                value = str(member.value)
                definition = enum_definition.permissible_values.get(value)
                if definition is None:
                    raise ValueError(
                        f"Generated enum {annotation.__name__} value {value!r} "
                        "is absent from the LinkML schema"
                    )
                values.append(
                    StateValue(
                        value=value,
                        description=_schema_annotation_value(
                            definition.annotations,
                            RELATION_EXTRACTION_PROMPT_ANNOTATION,
                        ),
                    )
                )
            attributes.append(
                StateAttribute(
                    name=name,
                    description=enum_definition.description
                    or field.description
                    or annotation.__name__,
                    values=tuple(values),
                )
            )
        if not attributes:
            raise ValueError(f"Object state {model.__name__} has no value fields")
        targets.append(
            StateTarget(
                model=model,
                description=_description(model),
                subject_model=subject_model,
                attributes=tuple(attributes),
            )
        )
    return tuple(sorted(targets, key=lambda target: target.model.__name__))


def state_subject_model(state: ObjectState | ObjectStateModel) -> RoadUserModel:
    """Return the road-user model accepted by one concrete state type."""

    state_model = state if isinstance(state, type) else type(state)
    for target in state_targets():
        if target.model is state_model:
            return target.subject_model
    raise ValueError(f"Unknown object state type: {state_model.__name__}")


def _descendants(model: type[Any]) -> tuple[type[Any], ...]:
    descendants: list[type[Any]] = []
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


def _schema_annotation_value(
    annotations: Mapping[str, object], name: str
) -> str:
    annotation = annotations.get(name)
    value = getattr(annotation, "value", None)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"LinkML permissible value needs a nonempty {name} annotation"
        )
    return value.strip()


def _description(model: type[Any]) -> str:
    description = inspect.getdoc(model)
    if not description:
        raise ValueError(f"LinkML class {model.__name__} needs a description")
    return description
