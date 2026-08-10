from __future__ import annotations

import json
import re
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from src.clients.vlm import VlmClient, VlmRequest
from src.frame import Frame
from src.graph._generated.catalog import OBJECT_TARGETS, RELATION_TARGETS
from src.graph._generated.models import (
    LaneDirection,
    LaneRelation,
    LeftAdjacentTo,
    ObjectDecision,
    ObjectProvenance,
    Provenance,
    Relation,
    RoadObject,
    RoadObjectRelation,
    SceneObject,
)
from src.graph.ontology import ObjectTarget, RelationTarget
from src.stage import StageOutput
from src.stages.vlm_helper import (
    build_request_trace,
    build_vlm_images,
    parse_vlm_json,
    render_identity_map,
)
from src.traces import JsonValue, Trace


class RoadObjectProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_id: str
    type: str
    attributes: dict[str, str]
    occupants: list[str]


class LaneRelationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    subject: str
    object: str


class RoadLayoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objects: list[RoadObjectProposal]
    relations: list[LaneRelationProposal]


class RoadLayoutExtractionStage:
    """Add ego-relevant lanes, lane membership, and lane topology."""

    name = "road-layout-extraction"

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        identity_map = render_identity_map(frame)
        registry_objects = [
            object_
            for object_ in frame.graph.objects
            if object_.id == "ego" or object_.bbox is not None
        ]
        registry: list[JsonValue] = [
            {"id": object_.id, "type": object_.type}
            for object_ in registry_objects
        ]
        object_targets = tuple(
            target
            for target in OBJECT_TARGETS
            if issubclass(target.model, RoadObject)
            and not target.model.model_fields["bbox"].is_required()
        )
        target_by_name = {
            target.model.__name__: target for target in object_targets
        }
        relation_targets = tuple(
            target
            for target in RELATION_TARGETS
            if issubclass(target.model, LaneRelation)
        )
        membership_models = {}
        for target in object_targets:
            candidates = [
                relation.model
                for relation in RELATION_TARGETS
                if issubclass(relation.model, RoadObjectRelation)
                and issubclass(target.model, relation.object_model)
            ]
            if len(candidates) != 1:
                raise ValueError(
                    f"Road layout type {target.model.__name__} needs exactly one "
                    f"membership relation, found {[model.__name__ for model in candidates]}"
                )
            membership_models[target.model] = candidates[0]
        relation_by_name = {
            target.model.__name__: target for target in relation_targets
        }
        vocabulary = _vocabulary_payload(object_targets, relation_targets)
        prompt = _build_prompt(registry, vocabulary)
        stage_input: dict[str, JsonValue] = {
            "objects": registry,
            "vocabulary": vocabulary,
        }

        response = self.client.complete(
            VlmRequest(
                prompt=prompt,
                images=build_vlm_images(frame, identity_map),
                response_schema=_response_schema(
                    object_targets, relation_targets
                ),
            )
        )
        proposals = RoadLayoutResponse.model_validate(
            parse_vlm_json(response.text)
        )
        _validate_proposals(
            proposals,
            known_occupants={object_.id for object_ in registry_objects},
            target_by_name=target_by_name,
            relation_by_name=relation_by_name,
        )

        used_object_ids = {object_.id for object_ in frame.graph.objects}
        next_object_index = {name: 1 for name in target_by_name}
        local_id_map: dict[str, str] = {}
        objects: list[SceneObject] = []
        normalized_objects: list[JsonValue] = []
        for proposal in proposals.objects:
            target = target_by_name[proposal.type]
            prefix = _snake_case(target.model.__name__)
            index = next_object_index[proposal.type]
            while f"{prefix}_{index:03d}" in used_object_ids:
                index += 1
            object_id = f"{prefix}_{index:03d}"
            next_object_index[proposal.type] = index + 1
            used_object_ids.add(object_id)
            local_id_map[proposal.local_id] = object_id

            object_ = target.model.model_validate(
                {
                    "id": object_id,
                    "provenance": [
                        ObjectProvenance(
                            source="vlm",
                            stage=self.name,
                            model=response.model,
                            supports=[
                                ObjectDecision.existence,
                                ObjectDecision.classification,
                                ObjectDecision.attributes,
                            ],
                        )
                    ],
                    **proposal.attributes,
                }
            )
            objects.append(object_)
            normalized_objects.append(
                cast(
                    JsonValue,
                    object_.model_dump(mode="json", exclude_none=True),
                )
            )

        relation_specs: list[tuple[type[Relation], str, str]] = []
        for proposal in proposals.objects:
            object_id = local_id_map[proposal.local_id]
            target = target_by_name[proposal.type]
            relation_specs.extend(
                (membership_models[target.model], occupant, object_id)
                for occupant in proposal.occupants
            )
        for proposal in proposals.relations:
            target = relation_by_name[proposal.type]
            subject = local_id_map[proposal.subject]
            object_ = local_id_map[proposal.object]
            if target.symmetric and subject > object_:
                subject, object_ = object_, subject
            relation_specs.append((target.model, subject, object_))

        used_relation_ids = {relation.id for relation in frame.graph.relations}
        relation_index = 1
        relations: list[Relation] = []
        normalized_relations: list[JsonValue] = []
        for relation_model, subject, object_ in relation_specs:
            while f"relation_{relation_index:03d}" in used_relation_ids:
                relation_index += 1
            relation_id = f"relation_{relation_index:03d}"
            relation_index += 1
            used_relation_ids.add(relation_id)
            relation = relation_model.model_validate(
                {
                    "id": relation_id,
                    "subject": subject,
                    "object": object_,
                    "provenance": [
                        Provenance(
                            source="vlm",
                            stage=self.name,
                            model=response.model,
                        )
                    ],
                }
            )
            relations.append(relation)
            normalized_relations.append(
                cast(
                    JsonValue,
                    relation.model_dump(mode="json", exclude_none=True),
                )
            )

        request_trace = build_request_trace(response)
        return StageOutput(
            objects=tuple(objects),
            relations=tuple(relations),
            traces=(
                Trace.text("prompt.txt", prompt),
                Trace.json("stage-input.json", stage_input),
                Trace.json("request.json", request_trace),
                Trace.bytes("identity-map.png", identity_map),
                Trace.json("response.raw.json", response.raw),
                Trace.text("response.txt", response.text),
                Trace.json("lanes.json", normalized_objects),
                Trace.json("relations.json", normalized_relations),
            ),
        )


def _vocabulary_payload(
    object_targets: tuple[ObjectTarget, ...],
    relation_targets: tuple[RelationTarget, ...],
) -> dict[str, JsonValue]:
    return {
        "object_types": [
            {
                "type": target.model.__name__,
                "description": target.description,
                "attributes": {
                    attribute.name: {
                        "description": attribute.description,
                        "required": attribute.required,
                        "values": [
                            {
                                "value": value.value,
                                "description": value.description,
                            }
                            for value in attribute.values
                        ],
                    }
                    for attribute in target.attributes
                },
            }
            for target in object_targets
        ],
        "relation_types": [
            {
                "type": target.model.__name__,
                "description": target.description,
            }
            for target in relation_targets
        ],
    }


def _snake_case(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def _build_prompt(
    registry: list[JsonValue], vocabulary: dict[str, JsonValue]
) -> str:
    return f"""Extract clear local lane topology for ego, the camera vehicle, from the original first image and labeled second image.
Include ego's lane and other relevant lanes. Assign local IDs for relations and use only registry IDs as occupants.

Registry: {json.dumps(registry, separators=(",", ":"))}
Vocabulary: {json.dumps(vocabulary, separators=(",", ":"))}
"""


def _validate_proposals(
    proposals: RoadLayoutResponse,
    *,
    known_occupants: set[str],
    target_by_name: dict[str, ObjectTarget],
    relation_by_name: dict[str, RelationTarget],
) -> None:
    proposal_by_local_id: dict[str, RoadObjectProposal] = {}
    occupant_lanes: dict[str, str] = {}
    for proposal in proposals.objects:
        if proposal.local_id in proposal_by_local_id:
            raise ValueError(f"Duplicate local lane ID: {proposal.local_id}")
        proposal_by_local_id[proposal.local_id] = proposal
        target = target_by_name.get(proposal.type)
        if target is None:
            raise ValueError(f"Unknown road-layout object type: {proposal.type}")
        expected_attributes = {
            attribute.name: attribute for attribute in target.attributes
        }
        required_attributes = {
            name for name, attribute in expected_attributes.items() if attribute.required
        }
        if not required_attributes.issubset(proposal.attributes):
            raise ValueError(
                f"{proposal.type} requires attributes {sorted(required_attributes)}"
            )
        if not set(proposal.attributes).issubset(expected_attributes):
            raise ValueError(
                f"{proposal.type} has unknown attributes "
                f"{sorted(set(proposal.attributes) - set(expected_attributes))}"
            )
        for name, value in proposal.attributes.items():
            valid_values = {
                item.value for item in expected_attributes[name].values
            }
            if value not in valid_values:
                raise ValueError(
                    f"Invalid value for {proposal.type}.{name}: {value!r}"
                )
        if len(proposal.occupants) != len(set(proposal.occupants)):
            raise ValueError(
                f"Lane {proposal.local_id} contains duplicate occupants"
            )
        for occupant in proposal.occupants:
            if occupant not in known_occupants:
                raise ValueError(f"Lane has unknown occupant: {occupant}")
            previous = occupant_lanes.get(occupant)
            if previous is not None:
                raise ValueError(
                    f"Object {occupant} occupies both {previous} and "
                    f"{proposal.local_id}"
                )
            occupant_lanes[occupant] = proposal.local_id

    if occupant_lanes.get("ego") is None:
        raise ValueError("Road layout must place ego in exactly one lane")

    relation_keys: set[tuple[str, str, str]] = set()
    symmetric_keys: set[tuple[str, str, str]] = set()
    right_by_left: dict[str, str] = {}
    left_by_right: dict[str, str] = {}
    for proposal in proposals.relations:
        target = relation_by_name.get(proposal.type)
        if target is None:
            raise ValueError(f"Unknown lane relation type: {proposal.type}")
        subject = proposal_by_local_id.get(proposal.subject)
        object_ = proposal_by_local_id.get(proposal.object)
        if subject is None or object_ is None:
            raise ValueError(
                f"Lane relation {proposal.type} has an unknown endpoint"
            )
        if proposal.subject == proposal.object:
            raise ValueError(f"Lane relation {proposal.type} cannot reference itself")
        key = (proposal.type, proposal.subject, proposal.object)
        if key in relation_keys:
            raise ValueError(f"Duplicate lane relation: {key}")
        relation_keys.add(key)
        if target.symmetric:
            symmetric_key = (
                proposal.type,
                *sorted((proposal.subject, proposal.object)),
            )
            if symmetric_key in symmetric_keys:
                raise ValueError(f"Duplicate symmetric lane relation: {symmetric_key}")
            symmetric_keys.add(symmetric_key)
        if target.model is LeftAdjacentTo:
            subject_direction = subject.attributes.get("direction")
            object_direction = object_.attributes.get("direction")
            if (
                subject_direction == LaneDirection.crossing.value
                or object_direction == LaneDirection.crossing.value
            ):
                raise ValueError(
                    f"{proposal.type} requires parallel non-crossing lanes"
                )
            previous_right = right_by_left.get(proposal.subject)
            if previous_right is not None:
                raise ValueError(
                    f"Lane {proposal.subject} has more than one direct right lane"
                )
            previous_left = left_by_right.get(proposal.object)
            if previous_left is not None:
                raise ValueError(
                    f"Lane {proposal.object} has more than one direct left lane"
                )
            right_by_left[proposal.subject] = proposal.object
            left_by_right[proposal.object] = proposal.subject


def _response_schema(
    object_targets: tuple[ObjectTarget, ...],
    relation_targets: tuple[RelationTarget, ...],
) -> dict[str, JsonValue]:
    object_variants: list[dict[str, Any]] = []
    for target in object_targets:
        attribute_properties = {
            attribute.name: {
                "type": "string",
                "enum": [value.value for value in attribute.values],
            }
            for attribute in target.attributes
        }
        required_attributes = [
            attribute.name for attribute in target.attributes if attribute.required
        ]
        object_variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "local_id": {"type": "string", "minLength": 1},
                    "type": {
                        "type": "string",
                        "enum": [target.model.__name__],
                    },
                    "attributes": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": attribute_properties,
                        "required": required_attributes,
                    },
                    "occupants": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["local_id", "type", "attributes", "occupants"],
            }
        )
    relation_variants = [
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "type": {
                    "type": "string",
                    "enum": [target.model.__name__],
                },
                "subject": {"type": "string"},
                "object": {"type": "string"},
            },
            "required": ["type", "subject", "object"],
        }
        for target in relation_targets
    ]
    return cast(
        dict[str, JsonValue],
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "objects": {
                    "type": "array",
                    "items": {"anyOf": object_variants},
                },
                "relations": {
                    "type": "array",
                    "items": {"anyOf": relation_variants},
                },
            },
            "required": ["objects", "relations"],
        },
    )
