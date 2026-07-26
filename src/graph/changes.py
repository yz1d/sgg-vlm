from __future__ import annotations

from dataclasses import dataclass

from src.graph.models import (
    ObjectState,
    PerceivedRoadUser,
    Provenance,
    SpatialRelationship,
)


@dataclass(frozen=True, slots=True)
class AddRoadUser:
    road_user: PerceivedRoadUser


@dataclass(frozen=True, slots=True)
class RefineRoadUserType:
    road_user_id: str
    new_type: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class SetTrackId:
    road_user_id: str
    track_id: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class AddRelationship:
    relationship: SpatialRelationship


@dataclass(frozen=True, slots=True)
class AddObjectState:
    road_user_id: str
    state: ObjectState


type SceneChange = (
    AddRoadUser
    | RefineRoadUserType
    | SetTrackId
    | AddRelationship
    | AddObjectState
)
