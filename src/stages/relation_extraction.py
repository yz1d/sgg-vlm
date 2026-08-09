from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from src.clients.vlm import VlmClient, VlmRequest
from src.frame import Frame
from src.graph._generated.catalog import OBJECT_ATTRIBUTE_TARGETS, RELATION_TARGETS
from src.graph._generated.models import (
    EgoVehicle,
    ObjectDecision,
    ObjectProvenance,
    Provenance,
    Relation,
    SceneObject,
)
from src.graph.ontology import ObjectAttributeTarget, RelationTarget
from src.stage import StageOutput
from src.stages.vlm_helper import (
    build_request_trace,
    build_vlm_images,
    parse_vlm_json,
    render_identity_map,
)
from src.traces import JsonValue, Trace


class RelationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    type: str


class ObjectAttributeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    name: str
    value: str


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relations: list[RelationProposal]
    attributes: list[ObjectAttributeProposal]


class RelationExtractionStage:
    """Add object-to-ego relations and schema-defined object attributes."""

    name = "relation-extraction"

    def __init__(self, client: VlmClient) -> None:
        self.client = client

    def run(self, frame: Frame) -> StageOutput:
        objects = [
            object_
            for object_ in frame.graph.objects
            if object_.id != "ego" and object_.bbox is not None
        ]
        ego = next(
            (
                object_
                for object_ in frame.graph.objects
                if isinstance(object_, EgoVehicle) and object_.id == "ego"
            ),
            None,
        )
        if ego is None:
            raise ValueError("Scene has no ego object")
        relation_vocabulary = tuple(
            target
            for target in RELATION_TARGETS
            if target.relation_extraction
        )
        attribute_vocabulary = tuple(
            target
            for target in OBJECT_ATTRIBUTE_TARGETS
            if any(isinstance(object_, target.object_model) for object_ in objects)
        )
        identity_map = render_identity_map(frame)
        registry: list[JsonValue] = [
            {"id": object_.id, "type": object_.type} for object_ in objects
        ]
        vocabulary = _vocabulary_payload(
            relation_vocabulary, attribute_vocabulary
        )
        prompt = _build_prompt(registry, vocabulary)
        stage_input: dict[str, JsonValue] = {
            "objects": registry,
            "vocabulary": vocabulary,
        }

        if not objects:
            return StageOutput(
                traces=(
                    Trace.text("prompt.txt", prompt),
                    Trace.json("stage-input.json", stage_input),
                    Trace.json("request.json", {"skipped": "no visible scene objects"}),
                    Trace.bytes("identity-map.png", identity_map),
                    Trace.json("relations.json", []),
                    Trace.json("object-attributes.json", []),
                )
            )

        response = self.client.complete(
            VlmRequest(
                prompt=prompt,
                images=build_vlm_images(frame, identity_map),
                response_schema=_response_schema(
                    objects,
                    relation_vocabulary,
                    attribute_vocabulary,
                ),
            )
        )
        proposals = ExtractionResponse.model_validate(
            parse_vlm_json(response.text)
        )
        object_by_id = {object_.id: object_ for object_ in objects}
        relation_by_name = {
            target.model.__name__: target for target in relation_vocabulary
        }
        _validate_proposals(
            proposals,
            object_by_id=object_by_id,
            relation_by_name=relation_by_name,
            attribute_targets=attribute_vocabulary,
        )

        used_relation_ids = {relation.id for relation in frame.graph.relations}
        relation_index = 1
        relations: list[Relation] = []
        normalized_relations: list[JsonValue] = []
        for proposal in proposals.relations:
            while f"relation_{relation_index:03d}" in used_relation_ids:
                relation_index += 1
            relation_id = f"relation_{relation_index:03d}"
            used_relation_ids.add(relation_id)
            relation_index += 1
            target = relation_by_name[proposal.type]
            relation = target.model.model_validate(
                {
                    "id": relation_id,
                    "subject": proposal.subject,
                    "object": ego.id,
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

        attribute_values_by_object: dict[str, dict[str, str]] = {}
        for proposal in proposals.attributes:
            attribute_values_by_object.setdefault(proposal.subject, {})[
                proposal.name
            ] = proposal.value

        updated_objects: list[SceneObject] = []
        normalized_attributes: list[JsonValue] = []
        for object_id, attribute_values in attribute_values_by_object.items():
            object_ = object_by_id[object_id]
            payload = object_.model_dump(mode="python")
            payload.update(attribute_values)
            payload["provenance"] = [
                *object_.provenance,
                ObjectProvenance(
                    source="vlm",
                    stage=self.name,
                    model=response.model,
                    supports=[ObjectDecision.attributes],
                ),
            ]
            updated = type(object_).model_validate(payload)
            updated_objects.append(updated)
            normalized_attributes.extend(
                {
                    "subject": object_id,
                    "name": name,
                    "value": value,
                }
                for name, value in attribute_values.items()
            )

        request_trace = build_request_trace(response)
        return StageOutput(
            objects=tuple(updated_objects),
            relations=tuple(relations),
            traces=(
                Trace.text("prompt.txt", prompt),
                Trace.json("stage-input.json", stage_input),
                Trace.json("request.json", request_trace),
                Trace.bytes("identity-map.png", identity_map),
                Trace.json("response.raw.json", response.raw),
                Trace.text("response.txt", response.text),
                Trace.json("relations.json", normalized_relations),
                Trace.json("object-attributes.json", normalized_attributes),
            ),
        )


def _vocabulary_payload(
    relations: tuple[RelationTarget, ...],
    attributes: tuple[ObjectAttributeTarget, ...],
) -> dict[str, JsonValue]:
    return {
        "relation_types": [
            {
                "type": target.model.__name__,
                "description": target.description,
                "subject_type": target.subject_model.__name__,
                "object_type": target.object_model.__name__,
                "exclusive_group": target.exclusive_group,
            }
            for target in relations
        ],
        "object_attributes": [
            {
                "object_type": target.object_model.__name__,
                "name": target.name,
                "description": target.description,
                "values": [
                    {
                        "value": value.value,
                        "description": value.description,
                        "visual_prompt": value.prompt,
                    }
                    for value in target.values
                ],
            }
            for target in attributes
        ],
    }


def _build_prompt(
    registry: list[JsonValue], vocabulary: dict[str, JsonValue]
) -> str:
    return f"""Extract clear schema-defined facts for these visible scene objects.

The first image is original. The second labels visible scene objects. Ego is the camera vehicle.
Every relation describes one registry object relative to ego.
Object attributes apply only to compatible object types in the vocabulary.
Use only registry IDs, relation types, attribute names, and attribute values from the vocabulary.
Return only clear visual facts. Omit uncertain attributes and relations.

Scene-object registry:
{json.dumps(registry, separators=(",", ":"))}

Schema vocabulary:
{json.dumps(vocabulary, separators=(",", ":"))}
"""


def _validate_proposals(
    proposals: ExtractionResponse,
    *,
    object_by_id: Mapping[str, SceneObject],
    relation_by_name: dict[str, RelationTarget],
    attribute_targets: tuple[ObjectAttributeTarget, ...],
) -> None:
    relation_keys: set[tuple[str, str]] = set()
    groups: set[tuple[str, str]] = set()
    for proposal in proposals.relations:
        object_ = object_by_id.get(proposal.subject)
        if object_ is None:
            raise ValueError(f"Relation has unknown subject: {proposal.subject}")
        target = relation_by_name.get(proposal.type)
        if target is None:
            raise ValueError(f"Unknown relation type: {proposal.type}")
        if not isinstance(object_, target.subject_model):
            raise ValueError(
                f"Relation {proposal.type} does not apply to {object_.type}"
            )
        key = (proposal.subject, proposal.type)
        if key in relation_keys:
            raise ValueError(f"Duplicate relation proposal: {key}")
        relation_keys.add(key)
        if target.exclusive_group is not None:
            group_key = (proposal.subject, target.exclusive_group)
            if group_key in groups:
                raise ValueError(
                    f"Conflicting {target.exclusive_group} relations for "
                    f"{proposal.subject}"
                )
            groups.add(group_key)

    attribute_keys: set[tuple[str, str]] = set()
    for proposal in proposals.attributes:
        object_ = object_by_id.get(proposal.subject)
        if object_ is None:
            raise ValueError(
                f"Object attribute has unknown subject: {proposal.subject}"
            )
        candidates = [
            target
            for target in attribute_targets
            if target.name == proposal.name
            and isinstance(object_, target.object_model)
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"Unknown attribute {proposal.name!r} for {object_.type}"
            )
        target = candidates[0]
        valid_values = {value.value for value in target.values}
        if proposal.value not in valid_values:
            raise ValueError(
                f"Invalid value for {object_.type}.{proposal.name}: "
                f"{proposal.value!r}"
            )
        key = (proposal.subject, proposal.name)
        if key in attribute_keys:
            raise ValueError(f"Duplicate object attribute proposal: {key}")
        attribute_keys.add(key)


def _response_schema(
    objects: list[SceneObject],
    relations: tuple[RelationTarget, ...],
    attributes: tuple[ObjectAttributeTarget, ...],
) -> dict[str, JsonValue]:
    relation_variants: list[dict[str, Any]] = []
    for target in relations:
        subjects = [
            object_.id
            for object_ in objects
            if isinstance(object_, target.subject_model)
        ]
        if not subjects:
            continue
        relation_variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "subject": {"type": "string", "enum": subjects},
                    "type": {
                        "type": "string",
                        "enum": [target.model.__name__],
                    },
                },
                "required": ["subject", "type"],
            }
        )

    attribute_variants: list[dict[str, Any]] = []
    for target in attributes:
        subjects = [
            object_.id
            for object_ in objects
            if isinstance(object_, target.object_model)
        ]
        if not subjects:
            continue
        attribute_variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "subject": {"type": "string", "enum": subjects},
                    "name": {"type": "string", "enum": [target.name]},
                    "value": {
                        "type": "string",
                        "enum": [value.value for value in target.values],
                    },
                },
                "required": ["subject", "name", "value"],
            }
        )

    relation_items: dict[str, Any] = (
        {"anyOf": relation_variants} if relation_variants else {}
    )
    attribute_items: dict[str, Any] = (
        {"anyOf": attribute_variants} if attribute_variants else {}
    )
    return cast(
        dict[str, JsonValue],
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "relations": {
                    "type": "array",
                    "items": relation_items,
                    **({"maxItems": 0} if not relation_variants else {}),
                },
                "attributes": {
                    "type": "array",
                    "items": attribute_items,
                    **({"maxItems": 0} if not attribute_variants else {}),
                },
            },
            "required": ["relations", "attributes"],
        },
    )
