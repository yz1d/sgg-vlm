from __future__ import annotations

from typing import Protocol

from src.graph.models import Scene, SchoolBus, StopArmState


class GraphValidationError(ValueError):
    """A complete graph violates its structural or semantic contract."""


class GraphValidator(Protocol):
    def validate(self, graph: Scene) -> None: ...


class DefaultGraphValidator:
    """Validate graph invariants not fully expressible in LinkML."""

    def validate(self, graph: Scene) -> None:
        road_users = graph.road_users or []
        relationships = graph.relationships or []
        road_user_ids = [road_user.id for road_user in road_users]
        if len(road_user_ids) != len(set(road_user_ids)):
            raise GraphValidationError("Road-user IDs must be unique")
        if "ego" in road_user_ids:
            raise GraphValidationError("The reserved ego ID cannot be a road user")

        for road_user in road_users:
            bbox = road_user.bbox
            if bbox.x_min > bbox.x_max or bbox.y_min > bbox.y_max:
                raise GraphValidationError(
                    f"Road user {road_user.id} has an invalid bounding box"
                )
            for state in road_user.states or []:
                if isinstance(state, StopArmState) and not isinstance(
                    road_user, SchoolBus
                ):
                    raise GraphValidationError(
                        "StopArmState applies only to SchoolBus road users"
                    )

        relationship_ids = [relationship.id for relationship in relationships]
        if len(relationship_ids) != len(set(relationship_ids)):
            raise GraphValidationError("Relationship IDs must be unique")
        known_subjects = set(road_user_ids)
        for relationship in relationships:
            if relationship.subject not in known_subjects:
                raise GraphValidationError(
                    f"Relationship {relationship.id} has unknown subject "
                    f"{relationship.subject}"
                )
            if relationship.object != "ego":
                raise GraphValidationError(
                    f"Relationship {relationship.id} must target ego"
                )
