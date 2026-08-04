from __future__ import annotations

from dataclasses import dataclass

from src.graph._generated.models import (
    ObjectState,
    PerceivedRoadEntity,
    PerceivedRoadUser,
    Relationship,
    RoadEntity,
    RoadRegion,
)


type PerceivedEntityModel = type[PerceivedRoadEntity]
type RoadUserModel = type[PerceivedRoadUser]
type RoadRegionModel = type[RoadRegion]
type RelationshipModel = type[Relationship]
type ObjectStateModel = type[ObjectState]
type EntityModel = type[RoadEntity] | type[RoadRegion]


@dataclass(frozen=True, slots=True)
class DetectionTarget:
    model: PerceivedEntityModel
    prompt: str


@dataclass(frozen=True, slots=True)
class RoadRegionTarget:
    model: RoadRegionModel
    description: str
    membership_model: RelationshipModel
    id_prefix: str


@dataclass(frozen=True, slots=True)
class RelationshipTarget:
    model: RelationshipModel
    description: str
    subject_model: EntityModel
    object_model: EntityModel
    exclusive_group: str | None
    extraction_enabled: bool


@dataclass(frozen=True, slots=True)
class StateValue:
    value: str
    description: str
    prompt: str


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
