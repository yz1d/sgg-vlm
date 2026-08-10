from __future__ import annotations

from dataclasses import dataclass

from src.graph._generated.models import Relation, SceneObject

type ObjectModel = type[SceneObject]
type RelationModel = type[Relation]


@dataclass(frozen=True, slots=True)
class AttributeValue:
    value: str
    description: str


@dataclass(frozen=True, slots=True)
class ObjectAttributeTarget:
    object_model: ObjectModel
    name: str
    description: str
    required: bool
    values: tuple[AttributeValue, ...]


@dataclass(frozen=True, slots=True)
class ObjectTarget:
    model: ObjectModel
    description: str
    attributes: tuple[ObjectAttributeTarget, ...]


@dataclass(frozen=True, slots=True)
class RelationTarget:
    model: RelationModel
    description: str
    subject_model: ObjectModel
    object_model: ObjectModel
    exclusive_group: str | None
    symmetric: bool
