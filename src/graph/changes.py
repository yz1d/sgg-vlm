from __future__ import annotations

from dataclasses import dataclass

from src.graph._generated.models import (
    ObjectState,
    PerceivedRoadUser,
    Relationship,
    RoadRegion,
)


@dataclass(frozen=True, slots=True)
class AddRoadUser:
    road_user: PerceivedRoadUser


@dataclass(frozen=True, slots=True)
class AddRoadRegion:
    road_region: RoadRegion


@dataclass(frozen=True, slots=True)
class AddRelationship:
    relationship: Relationship


@dataclass(frozen=True, slots=True)
class AddObjectState:
    state: ObjectState


type SceneChange = (
    AddRoadUser | AddRoadRegion | AddRelationship | AddObjectState
)
