from __future__ import annotations

from dataclasses import dataclass

from src.graph.models import ObjectState, PerceivedRoadUser, SpatialRelationship


@dataclass(frozen=True, slots=True)
class AddRoadUser:
    road_user: PerceivedRoadUser


@dataclass(frozen=True, slots=True)
class AddRelationship:
    relationship: SpatialRelationship


@dataclass(frozen=True, slots=True)
class AddObjectState:
    road_user_id: str
    state: ObjectState


type SceneChange = AddRoadUser | AddRelationship | AddObjectState
