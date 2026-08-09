from __future__ import annotations

from src.graph._generated.catalog import RELATION_TARGETS
from src.graph._generated.models import EgoVehicle, LaneDirection, Scene


class GraphValidationError(ValueError):
    """A complete graph violates its semantic contract."""


def validate_scene(graph: Scene) -> None:
    """Validate graph invariants that require comparisons across records."""

    object_ids = [object_.id for object_ in graph.objects]
    if len(object_ids) != len(set(object_ids)):
        raise GraphValidationError("Object IDs must be unique")

    ego_objects = [
        object_
        for object_ in graph.objects
        if isinstance(object_, EgoVehicle) and object_.id == "ego"
    ]
    if len(ego_objects) != 1:
        raise GraphValidationError("The scene must contain exactly one ego object")
    if any(
        object_.id == "ego" and not isinstance(object_, EgoVehicle)
        for object_ in graph.objects
    ):
        raise GraphValidationError("Only EgoVehicle can use the ego ID")
    if ego_objects[0].bbox is not None:
        raise GraphValidationError("The ego object cannot have an image bounding box")

    for object_ in graph.objects:
        bbox = object_.bbox
        if bbox is None:
            continue
        if bbox.x_min > bbox.x_max or bbox.y_min > bbox.y_max:
            raise GraphValidationError(
                f"Object {object_.id} has an invalid bounding box"
            )

    relation_ids = [relation.id for relation in graph.relations]
    if len(relation_ids) != len(set(relation_ids)):
        raise GraphValidationError("Relation IDs must be unique")
    relation_keys = [
        (relation.subject, relation.type, relation.object)
        for relation in graph.relations
    ]
    if len(relation_keys) != len(set(relation_keys)):
        raise GraphValidationError(
            "Relations must be unique by subject, type, and object"
        )

    object_by_id = {object_.id: object_ for object_ in graph.objects}
    target_by_type = {
        target.model.__name__: target for target in RELATION_TARGETS
    }
    relation_groups: set[tuple[str, str]] = set()
    symmetric_keys: set[tuple[str, str, str]] = set()
    adjacency_pairs: set[frozenset[str]] = set()
    right_by_left: dict[str, str] = {}
    left_by_right: dict[str, str] = {}
    for relation in graph.relations:
        target = target_by_type[relation.type]
        subject = object_by_id.get(relation.subject)
        if subject is None:
            raise GraphValidationError(
                f"Relation {relation.id} has unknown subject {relation.subject}"
            )
        if not isinstance(subject, target.subject_model):
            raise GraphValidationError(
                f"Relation {relation.id} requires subject type "
                f"{target.subject_model.__name__}"
            )
        object_ = object_by_id.get(relation.object)
        if object_ is None:
            raise GraphValidationError(
                f"Relation {relation.id} has unknown object {relation.object}"
            )
        if not isinstance(object_, target.object_model):
            raise GraphValidationError(
                f"Relation {relation.id} requires object type "
                f"{target.object_model.__name__}"
            )
        if relation.subject == relation.object:
            raise GraphValidationError(
                f"Relation {relation.id} cannot reference one object twice"
            )
        if target.exclusive_group is not None:
            key = (relation.subject, target.exclusive_group)
            if key in relation_groups:
                raise GraphValidationError(
                    f"Object {relation.subject} has more than one "
                    f"{target.exclusive_group} relation"
                )
            relation_groups.add(key)
        if target.symmetric:
            key = (
                relation.type,
                *sorted((relation.subject, relation.object)),
            )
            if key in symmetric_keys:
                raise GraphValidationError(
                    f"Relation {relation.type} repeats a symmetric object pair"
                )
            symmetric_keys.add(key)
            if relation.subject > relation.object:
                raise GraphValidationError(
                    f"Relation {relation.id} does not use canonical endpoint order"
                )
        if target.topology_constraint == "parallel_without_physical_separator":
            subject_direction = getattr(subject, "direction", None)
            object_direction = getattr(object_, "direction", None)
            if (
                subject_direction == LaneDirection.crossing
                or object_direction == LaneDirection.crossing
            ):
                raise GraphValidationError(
                    f"Relation {relation.id} requires parallel non-crossing lanes"
                )
            pair = frozenset((relation.subject, relation.object))
            if pair in adjacency_pairs:
                raise GraphValidationError(
                    f"Lane adjacency repeats pair {sorted(pair)}"
                )
            adjacency_pairs.add(pair)
            if relation.subject in right_by_left:
                raise GraphValidationError(
                    f"Lane {relation.subject} has more than one direct right lane"
                )
            if relation.object in left_by_right:
                raise GraphValidationError(
                    f"Lane {relation.object} has more than one direct left lane"
                )
            right_by_left[relation.subject] = relation.object
            left_by_right[relation.object] = relation.subject
