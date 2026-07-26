from __future__ import annotations

from typing import Protocol


class Provenance(Protocol):
    """Temporary typing surface for the generated LinkML provenance model."""

    source: str
    stage: str


class ObjectState(Protocol):
    """Temporary typing surface for generated object-state models."""

    type: str
    confidence: float | None
    provenance: list[Provenance]


class PerceivedRoadUser(Protocol):
    """Temporary typing surface for generated perceived-road-user models."""

    id: str
    type: str
    states: list[ObjectState] | None


class SpatialRelationship(Protocol):
    """Temporary typing surface for generated spatial-relationship models."""

    id: str
    type: str
    subject: str
    object: str


class Scene(Protocol):
    """Temporary typing surface for the generated LinkML Scene model."""

    frame_id: str
    road_users: list[PerceivedRoadUser]
    relationships: list[SpatialRelationship]
