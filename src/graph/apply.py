from __future__ import annotations

from typing import Protocol, Sequence

from src.graph.changes import (
    AddObjectState,
    AddRelationship,
    AddRoadRegion,
    AddRoadUser,
    SceneChange,
)
from src.graph._generated.models import Scene


class GraphChangeError(ValueError):
    """A requested semantic change violates graph-domain rules."""


class GraphChangeApplier(Protocol):
    """Applies semantic changes atomically to a graph copy."""

    def apply(self, graph: Scene, changes: Sequence[SceneChange]) -> Scene: ...


class DefaultGraphChangeApplier:
    """Apply the controlled graph operations exposed to pipeline stages."""

    def apply(self, graph: Scene, changes: Sequence[SceneChange]) -> Scene:
        updated = graph.model_copy(deep=True)
        for change in changes:
            if isinstance(change, AddRoadUser):
                self._add_road_user(updated, change)
            elif isinstance(change, AddRoadRegion):
                self._add_road_region(updated, change)
            elif isinstance(change, AddRelationship):
                self._add_relationship(updated, change)
            elif isinstance(change, AddObjectState):
                self._add_object_state(updated, change)
            else:
                raise GraphChangeError(
                    f"Unsupported graph change: {type(change).__name__}"
                )
        return Scene.model_validate(updated.model_dump(mode="python"))

    @staticmethod
    def _add_road_user(graph: Scene, change: AddRoadUser) -> None:
        road_users = list(graph.road_users or [])
        if any(road_user.id == change.road_user.id for road_user in road_users):
            raise GraphChangeError(f"Duplicate road-user ID: {change.road_user.id}")
        road_users.append(change.road_user)
        graph.road_users = road_users

    @staticmethod
    def _add_road_region(graph: Scene, change: AddRoadRegion) -> None:
        road_regions = list(graph.road_regions or [])
        if any(
            road_region.id == change.road_region.id
            for road_region in road_regions
        ):
            raise GraphChangeError(
                f"Duplicate road-region ID: {change.road_region.id}"
            )
        road_regions.append(change.road_region)
        graph.road_regions = road_regions

    @staticmethod
    def _add_object_state(graph: Scene, change: AddObjectState) -> None:
        states = list(graph.states or [])
        candidate = change.state
        if any(
            state.subject == candidate.subject and state.type == candidate.type
            for state in states
        ):
            raise GraphChangeError(
                f"Road user {candidate.subject} already has state {candidate.type}"
            )
        states.append(candidate)
        graph.states = states

    @staticmethod
    def _add_relationship(graph: Scene, change: AddRelationship) -> None:
        relationships = list(graph.relationships or [])
        candidate = change.relationship
        if any(relationship.id == candidate.id for relationship in relationships):
            raise GraphChangeError(f"Duplicate relationship ID: {candidate.id}")
        if any(
            relationship.subject == candidate.subject
            and relationship.type == candidate.type
            and relationship.object == candidate.object
            for relationship in relationships
        ):
            raise GraphChangeError(
                "Duplicate relationship: "
                f"({candidate.subject}, {candidate.type}, {candidate.object})"
            )
        relationships.append(candidate)
        graph.relationships = relationships
