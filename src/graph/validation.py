from __future__ import annotations

from typing import Protocol

from src.graph.extraction import relationship_targets, state_subject_model
from src.graph.models import (
    InIntersection,
    InLane,
    Intersection,
    Lane,
    RoadRegionRelationship,
    Scene,
    SpatialRelationship,
)


class GraphValidationError(ValueError):
    """A complete graph violates its structural or semantic contract."""


class GraphValidator(Protocol):
    def validate(self, graph: Scene) -> None: ...


class DefaultGraphValidator:
    """Validate graph invariants not fully expressible in LinkML."""

    def validate(self, graph: Scene) -> None:
        road_users = graph.road_users or []
        road_regions = graph.road_regions or []
        states = graph.states or []
        relationships = graph.relationships or []
        road_user_ids = [road_user.id for road_user in road_users]
        if len(road_user_ids) != len(set(road_user_ids)):
            raise GraphValidationError("Road-user IDs must be unique")
        if "ego" in road_user_ids:
            raise GraphValidationError("The reserved ego ID cannot be a road user")

        road_region_ids = [road_region.id for road_region in road_regions]
        if len(road_region_ids) != len(set(road_region_ids)):
            raise GraphValidationError("Road-region IDs must be unique")
        entity_ids = ["ego", *road_user_ids, *road_region_ids]
        if len(entity_ids) != len(set(entity_ids)):
            raise GraphValidationError("Entity IDs must be unique")

        for road_user in road_users:
            bbox = road_user.bbox
            if bbox.x_min > bbox.x_max or bbox.y_min > bbox.y_max:
                raise GraphValidationError(
                    f"Road user {road_user.id} has an invalid bounding box"
                )

        road_user_by_id = {road_user.id: road_user for road_user in road_users}
        state_keys = [(state.subject, state.type) for state in states]
        if len(state_keys) != len(set(state_keys)):
            raise GraphValidationError(
                "Object-state types must be unique for each road user"
            )
        for state in states:
            subject = road_user_by_id.get(state.subject)
            if subject is None:
                raise GraphValidationError(
                    f"Object state {state.type} has unknown subject {state.subject}"
                )
            try:
                expected_subject = state_subject_model(state)
            except ValueError as exc:
                raise GraphValidationError(str(exc)) from exc
            if not isinstance(subject, expected_subject):
                raise GraphValidationError(
                    f"Object state {state.type} requires "
                    f"{expected_subject.__name__}, got {subject.type}"
                )

        relationship_ids = [relationship.id for relationship in relationships]
        if len(relationship_ids) != len(set(relationship_ids)):
            raise GraphValidationError("Relationship IDs must be unique")
        road_region_by_id = {
            road_region.id: road_region for road_region in road_regions
        }
        known_road_users = {"ego", *road_user_ids}
        exclusive_group_by_type = {
            target.model.__name__: target.exclusive_group
            for target in relationship_targets()
            if target.exclusive_group is not None
        }
        for relationship_type in (InLane, InIntersection):
            annotation = relationship_type.linkml_meta.root["annotations"][
                "exclusive_group"
            ]
            exclusive_group_by_type[relationship_type.__name__] = annotation[
                "value"
            ]

        relationship_groups: set[tuple[str, str]] = set()
        for relationship in relationships:
            if isinstance(relationship, SpatialRelationship):
                if relationship.subject not in road_user_ids:
                    raise GraphValidationError(
                        f"Relationship {relationship.id} has unknown subject "
                        f"{relationship.subject}"
                    )
                if relationship.object != "ego":
                    raise GraphValidationError(
                        f"Relationship {relationship.id} must target ego"
                    )
            elif isinstance(relationship, RoadRegionRelationship):
                if relationship.subject not in known_road_users:
                    raise GraphValidationError(
                        f"Relationship {relationship.id} has unknown subject "
                        f"{relationship.subject}"
                    )
                road_region = road_region_by_id.get(relationship.object)
                if road_region is None:
                    raise GraphValidationError(
                        f"Relationship {relationship.id} has unknown object "
                        f"{relationship.object}"
                    )
                if isinstance(relationship, InLane) and not isinstance(
                    road_region, Lane
                ):
                    raise GraphValidationError(
                        f"Relationship {relationship.id} must target a lane"
                    )
                if isinstance(relationship, InIntersection) and not isinstance(
                    road_region, Intersection
                ):
                    raise GraphValidationError(
                        f"Relationship {relationship.id} must target an intersection"
                    )
            else:
                raise GraphValidationError(
                    f"Unsupported relationship type: {relationship.type}"
                )

            exclusive_group = exclusive_group_by_type.get(relationship.type)
            if exclusive_group is not None:
                key = (relationship.subject, exclusive_group)
                if key in relationship_groups:
                    raise GraphValidationError(
                        f"Road user {relationship.subject} has more than one "
                        f"{exclusive_group} relationship"
                    )
                relationship_groups.add(key)
