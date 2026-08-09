from __future__ import annotations

from dataclasses import dataclass

from src.graph._generated.models import Relation, RoadObject, SceneObject


type ObjectModel = type[SceneObject]
type RoadObjectModel = type[RoadObject]
type RelationModel = type[Relation]


@dataclass(frozen=True, slots=True)
class DetectionTarget:
    model: ObjectModel
    prompt: str


@dataclass(frozen=True, slots=True)
class AttributeValue:
    value: str
    description: str
    prompt: str


@dataclass(frozen=True, slots=True)
class ObjectAttributeTarget:
    object_model: ObjectModel
    name: str
    description: str
    required: bool
    values: tuple[AttributeValue, ...]


@dataclass(frozen=True, slots=True)
class RoadLayoutTarget:
    model: RoadObjectModel
    description: str
    membership_model: RelationModel
    id_prefix: str
    attributes: tuple[ObjectAttributeTarget, ...]


@dataclass(frozen=True, slots=True)
class RelationTarget:
    model: RelationModel
    description: str
    subject_model: ObjectModel
    object_model: ObjectModel
    exclusive_group: str | None
    relation_extraction: bool
    road_layout_extraction: bool
    topology_constraint: str | None
    symmetric: bool
