from __future__ import annotations

from src.graph._generated.catalog import RELATIONSHIP_TARGETS, STATE_TARGETS
from src.graph._generated.models import Scene


class GraphValidationError(ValueError):
    """A complete graph violates its semantic contract."""


def validate_scene(graph: Scene) -> None:
    """Validate graph invariants that require comparisons across records."""

    road_users = graph.road_users or []
    road_regions = graph.road_regions or []
    states = graph.states or []
    relationships = graph.relationships or []

    for road_user in road_users:
        bbox = road_user.bbox
        if bbox.x_min > bbox.x_max or bbox.y_min > bbox.y_max:
            raise GraphValidationError(
                f"Road user {road_user.id} has an invalid bounding box"
            )

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

    road_user_by_id = {road_user.id: road_user for road_user in road_users}
    state_target_by_type = {
        target.model.__name__: target for target in STATE_TARGETS
    }
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
        target = state_target_by_type[state.type]
        if not isinstance(subject, target.subject_model):
            raise GraphValidationError(
                f"Object state {state.type} requires "
                f"{target.subject_model.__name__}, got {subject.type}"
            )

    relationship_ids = [relationship.id for relationship in relationships]
    if len(relationship_ids) != len(set(relationship_ids)):
        raise GraphValidationError("Relationship IDs must be unique")
    entity_by_id = {
        "ego": graph.ego,
        **road_user_by_id,
        **{road_region.id: road_region for road_region in road_regions},
    }
    relationship_target_by_type = {
        target.model.__name__: target for target in RELATIONSHIP_TARGETS
    }
    relationship_groups: set[tuple[str, str]] = set()
    for relationship in relationships:
        target = relationship_target_by_type[relationship.type]
        subject = entity_by_id.get(relationship.subject)
        if subject is None:
            raise GraphValidationError(
                f"Relationship {relationship.id} has unknown subject "
                f"{relationship.subject}"
            )
        if not isinstance(subject, target.subject_model):
            raise GraphValidationError(
                f"Relationship {relationship.id} requires subject type "
                f"{target.subject_model.__name__}"
            )
        object_ = entity_by_id.get(relationship.object)
        if object_ is None:
            raise GraphValidationError(
                f"Relationship {relationship.id} has unknown object "
                f"{relationship.object}"
            )
        if not isinstance(object_, target.object_model):
            raise GraphValidationError(
                f"Relationship {relationship.id} requires object type "
                f"{target.object_model.__name__}"
            )
        if target.exclusive_group is not None:
            key = (relationship.subject, target.exclusive_group)
            if key in relationship_groups:
                raise GraphValidationError(
                    f"Road user {relationship.subject} has more than one "
                    f"{target.exclusive_group} relationship"
                )
            relationship_groups.add(key)
